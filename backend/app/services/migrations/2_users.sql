
-- Initialize some default users if they don't already exist.
-- The password is "password123" for each user, and we just entered the argon2 hash
-- Kind of primitive doing things like this, but it's pretty straight forward and gets the job done.

-- $argon2id$v=19$m=65536,t=3,p=4$4mPSKaKx/G34PYo+JEDHRw$zme15QAMHecvFasCAD4CLQ1YvwQF68nLql9lvmPqS38

INSERT INTO users 
  (email, full_name, is_admin, password_hash) 
VALUES (
  'nguyekev@iu.edu', 
  'Kevin Nguyen',
  TRUE,
  '$argon2id$v=19$m=65536,t=3,p=4$4mPSKaKx/G34PYo+JEDHRw$zme15QAMHecvFasCAD4CLQ1YvwQF68nLql9lvmPqS38'
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users 
  (email, full_name, is_admin, password_hash) 
VALUES (
  'john-admin@example.com', 
  'John Admin',
  TRUE,
  '$argon2id$v=19$m=65536,t=3,p=4$4mPSKaKx/G34PYo+JEDHRw$zme15QAMHecvFasCAD4CLQ1YvwQF68nLql9lvmPqS38'
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users 
  (email, full_name, is_admin, password_hash) 
VALUES (
  'dan-user@example.com', 
  'Dan User',
  FALSE,
  '$argon2id$v=19$m=65536,t=3,p=4$4mPSKaKx/G34PYo+JEDHRw$zme15QAMHecvFasCAD4CLQ1YvwQF68nLql9lvmPqS38'
) ON CONFLICT (email) DO NOTHING;
