import threading, time





class SnowflakeGenerator:
  def __init__(self, worker_id: int = 0, epoch: int = 1288834974657):
    """
    Generates Twitter-style Snowflake IDs
    
    64-bit structure:
    - 1 bit: unused (always 0)
    - 41 bits: timestamp (milliseconds since custom epoch)
    - 10 bits: machine/datacenter ID (5 + 5 bits). Here we'll just use machine_id to keep it simple.
    - 12 bits: sequence number

    Note:
    For personal projects, threadsafe custom code is fine. But for production and distributed systems 
    you'd need to get other details right (clock drift, worker-id assignment, cross-process safety)
    So sometimes you'll prefer a battle-tested library or something more simple

    - Worker ID Assignment: Each worker/machine that generates your snowflake IDs needs to have a unique ID.
      It doesn't have to be too complex, imagine worker 1 has ID 'A' and worker 2 has id 'B', etc. Use config,
      orchestration, or some kind of coordination service to make this happen.
    - Clock skew/backwards time: If a system clock goes backwards, you must decide: wait until clock catches up (simple),
      use logical clock bump, or fail fast. This situation happens when we see a smaller timestamp 
      than we saw a moment ago. This can happen if someone (e.g. admin) changes the system time backwards, 
      such as to fix some timezone error, or do something. Or it could be when your OS syncs with an NTP server and 
      the server finds that your clock is ahead of the real time. Your OS will need to correct course. Or when you're 
      working with VMs or containers and you're paused, etc. Teh virtual clock can jump around sometimes.
    - Multiple processes on the same host: You want to protect threads. Another setup is separate processes needing separate 
      coordination. So either unique worker_id per process or a shared allocator
    - Sequence Overflow: Your sequence number maximum is typically 2^{12}-1=4095, so 0 to 4095 is what your 12 bits cover. 
      You're able to generate 4096 snowflake ids per millisecond, but what happens if you hit the maximum? 
      Your code needs to wait until the next millisecond
    - 64-bit safety: Python 'int' is unbounded but systems are expecting a 64-bit unsigned/signed range. 
    """

    '''
    ##### Constants #####

    - max_worker_id: With this, you're going to have a maximum number of workers. This is 
      given by 1 * 2^{self.worker_id_bits} - 1.
    - max_sequence: The maximum sequence number that we can use when creating that id. Again this is 
      given by 1 * 2^{self.sequence_bits} - 1. 
    '''
    
    self.worker_id_bits = 10
    self.sequence_bits = 12

    self.worker_id = worker_id
    self.max_worker_id = (1 << self.worker_id_bits) - 1
    self.max_sequence = (1 << self.sequence_bits) - 1

    if not (0 <= self.worker_id <= self.max_worker_id):
        raise ValueError(f"worker_id must be 0..{self.max_worker_id}")

    self.worker_id = worker_id
    self.epoch = epoch  # in milliseconds

    '''
    ##### Bit shifts #####
    These are positional offsets in our 64-bit layout. Remember that snowflake ids 
    have parts. [timestamp | worker_id | sequence]
    
    There is no sequence shift because we plan those bits to be at the bottom of our snowflake 
    ID. We don't need to shift anything. However you know that worker_id needs to be 
    placed above the sequence bits. So we need to shift it to the left by sequence_bits 
    amount of times so that it is to the left of the sequence bits. Then the timestamp 
    is the largest field, and the contents of that field need to be to the left of both the sequence
    bits and the worker id bits. When you create your snowflake id, you can more easily shift the content around.
    '''
    self.worker_id_shift = self.sequence_bits
    self.timestamp_shift = self.worker_id_bits + self.sequence_bits

    '''
    ##### Runtime state #####
    We want a threading lock so that only one thread ata time can generate 
    an ID. This is because if somehow we had two threads generating IDs, 
    there's a chance we could have them generating it at the exact 
    same time (same timestamp, same millisecond), and since it's on different threads 
    we may also get the same sequence number, which is an issue as that causes
    the same UID to be generated (collisions!). This lock protects only within a single Python Process. That's fine, but 
    just know that if we run multiple API processes or on multipel servers, 
    each one needs a different worker_id to avoid "cross-process" collisions. 
    This is the idea of multiple hosts. It's fine if multiple hosts exist, 
    just we need each snowflake generator to have its own unique worker id, 
    which shouldn't be that hard.

    - one api process on one server: You only have one generator, you'll put a 
    worker id, but it doesn't really matter. A lock still helps prevent collisions.
    - Multiple api processes on one server: Assign unique worker id to each one.
    
    last_timestamp tracks the last millisecond for which we generated an ID.
    This is important because if a couple of "generate_id" calls were made 
    within the same millisecond, we know that we want to increment the sequence 
    number instead of resetting it. Also we're here to detect time gonig backwards.

    sequence: A per millisecond counter t oallow multiple IDs within the same 
    millisecond from the same order.    
    '''
    self.lock = threading.Lock()
    self.last_timestamp = -1
    self.sequence = 0
    
  def _current_timestamp(self):
    """Get the current timestamp in milliseconds"""
    return int(time.time() * 1000)
  
  def _wait_next_millisecond(self, last_timestamp):
    """Return the timestamp for the next millisecond"""
    timestamp = self._current_timestamp()
    while timestamp <= last_timestamp:
      timestamp = self._current_timestamp()
    return timestamp
  
  def next_id(self):
    '''Generates a unique Snowflake ID'''
    with self.lock:
      timestamp = self._current_timestamp()

      # Check for clock moving backwards
      if timestamp < self.last_timestamp:
        raise Exception(f"Clock moved backwards. Refusing to generate ID for {self.last_timestamp - timestamp} milliseconds")
       
      if timestamp == self.last_timestamp:
        '''
        ## If generating ID within the same millisecond

        Increments sequence by 1, and sequence == max_sequence_num, we set self.sequence = 0. We're 
        forcing an overflow/wrap around. 
        1. Remember that mean_sequence is the largest number you can represent in 12 bits, 4095 or 0b1111 1111 1111.
        2. Now with that complex bitmask:
          - Increment self.sequence
          - Use a bitwise AND to keep track of the lowest 12 bits of the result.
        3. Simulating the scenario under normal counting. Let's say max = 0b111 = 7.
          - if after increment as had 6 (0b110), our sequence number will stay 6. AND operation designed to keep 1s and 0s.
          - if after increment we get 7 (0b111), our sequence number stays 7
          - If you get 8 (0b1000), that's too big for our 3bit number to represent. When we do our AND comparison
            we'd compare 0b1000 to 0b111, which would compare the lower 3 bits and result in setting self.sequence = 0. This overflow will be 
            the only time where this happens.
        4. We overflowed and had to reset sequence = 0, so that means we'll wait for next millisecond since we 
        reset our count.
        '''
        self.sequence = (self.sequence + 1) & self.max_sequence_num
        if self.sequence == 0:
          timestamp = self._wait_next_millisecond(self.last_timestamp)
      else:
        # Else it's a new millisecond, so reset the sequence number to zero
        self.sequence_num = 0    

      # Always track when the last snowflake id was generated.
      self.last_timestamp = timestamp

    
      ''' 
      ## Generate snowflake ID
      Subtract from our epoch which is standard for snowflake ids. It makes sure that the number fits in 41 bits instead of 
      being a huge unix timestamp. We move hte timestamp tothe leftmost section of the snowflake id. We put the worker id just below 
      the timestamp bits. Then the sequence is in the lowest bits, so no shift is needed. The bitwise or thing just merges all of our 
      fields together.
      '''
      snowflake_id = (
          ((timestamp - self.epoch) << self.timestamp_shift) |
          (self.worker_id << self.worker_id_shift) |
          self.sequence 
      )

      return snowflake_id
