from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.services.auth_utils import require_auth, require_admin, create_user_info_list
from app.services.cassandra import cassandra_url_by_user_repo
from app.repositories.PostgresUserRepo import PostgresUserRepo, get_user_repo
from app.repositories.PostgresSessionRepo import PostgresSessionRepo, get_session_repo
from app.services.logger import app_logger

user_router = APIRouter()

# # ------------------------------------
# User Routes
# # ------------------------------------

# TODO: Verify this once url-router and service logic works correctly.
@user_router.get("/api/users/{user_id}/urls")
def get_urls_for_user(user_id: str, auth_user_id: str = Depends(require_auth)):
  """Gets all urls for an authenticated user

  Args:
      user_id (str): ID of the user whose urls we want to see.
      auth_user_id (str): ID of the user making the request

  Note: In the normal case, both should be equal. The only exceptions would 
  be when one user is trying to see another user's URLs. We prevent this entirely.
  Currently I don't see a reason for an admin to see someone else's urls, so 
  for now admins won't be able to see other people's urls either.
  """
  if user_id != auth_user_id:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Unauthorized to access these resources"
    )

  urls = cassandra_url_by_user_repo.get_urls_by_user_id(user_id)
  return urls

@user_router.get("/api/users")
async def get_users(user_id: int = Depends(require_admin), postgres_user_repo: PostgresUserRepo = Depends(get_user_repo)):
  """Gets all users in the application
  
  Note: Ideally we show all users on an admin dashboard.
  """
  users = await postgres_user_repo.get_all_users()
  users = create_user_info_list(users)
  return users

@user_router.delete("/api/users/{user_id}")
async def delete_user(user_id: int, auth_user_id: int = Depends(require_auth), postgres_user_repo: PostgresUserRepo = Depends(get_user_repo), postgres_session_repo: PostgresSessionRepo = Depends(get_session_repo)):
  """API endpoint for deleting a given user

  Args:
      user_id (str): ID of the user being deleted.
      auth_user_id (str): The ID of the user making the request.

  NOTE: Endpoint never actually verifies whether a user did exist and was deleted, but honestly
  that's fine for now. Unless the implementation would be really easy.
  """

  # Get the user who is making this request
  auth_user = await postgres_user_repo.get_user_by_id(auth_user_id)
  if not auth_user:
    # NOTE: This is just defensive programming in case for some reason the session
    # still exists, but the user doesn't for some reason. In a real world scenario, 
    # this will probably never happen.
    app_logger.warning(f"Session with user_id '{user_id}', but the user themselves did not exist in the db!")
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="User authenticating wasn't found!"
    )
  
  # Admins can't delete themselves
  if user_id == auth_user_id and auth_user["is_admin"]:
    app_logger.warning(f"Admin with id '{user_id}', attempted to delete themselves!")
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Admins cannot delete their own accounts!"
    )
  
  # If the authenticated user is trying to delete another user:
  # - If regular user is trying to delete another user, deny it
  # - Else admin is deleting another user, allow it
  is_admin_deletion = False
  if user_id != auth_user_id:
    if not auth_user["is_admin"]:
      app_logger.warning(f"User with id '{user_id}', attempted to delete another user!")
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unauthorized deletion!"
      )
    is_admin_deletion = True

  deletion_count = await postgres_user_repo.delete_user_by_id(user_id)
  if deletion_count != 1:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with ID '{user_id}' wasn't found. No deletion occurred!"
    )

  if is_admin_deletion:
    app_logger.info(f"Admin with ID '{auth_user_id}' deleted user with ID '{user_id}'.")
    return {"message": f"User id='{user_id}', deleted by admin"}
  app_logger.info(f"User with ID '{user_id}' deleted their own account!")
  return {"message": f"User id='{user_id}' is deleted"}

@user_router.patch("/api/users/{user_id}/admin")
async def change_admin_status(
  user_id: int, 
  # NOTE: ... makes it a required query param
  is_admin: bool = Query(..., description="Set to true or false to change admin status"),
  auth_user_id: str = Depends(require_admin), 
  postgres_user_repo: PostgresUserRepo = Depends(get_user_repo),
  postgres_session_repo: PostgresSessionRepo = Depends(get_session_repo)
  ):
  """Endpoint for letting an admin toggle the admin status of another user.

  Args:
      user_id (str): ID of the user whose admin status we're updating
      is_admin (bool): Boolean that we'll set the user's admin status to.
      auth_user_id (str): ID of the user making the request to update the admin status. This user is an admin.
  
  NOTE: I imagine this endpoint being used in an admin dashboard.
  """

  '''
  - If the user (an admin) is trying to change their own status, prevent them.
  - Else the user is trying to change someone else's status, which is good:
    1. Update the target user (handle non existence check and message), can be done in one query
    2. Delete the target user's current session (done in one query)
  '''
  if user_id == auth_user_id:
    app_logger.warning(f"Admin with ID '{user_id}' attempted to change their admin status.")
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Admins cannot change their own statuses!"
    )  

  update_count = await postgres_user_repo.update_is_admin_by_id(is_admin, user_id)
  if update_count != 1:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with ID '{user_id}' wasn't found. No updates occurred!"
    )

  await postgres_session_repo.delete_session_by_user_id(user_id)
  app_logger.info(f"User with ID '{user_id}' now has is_admin={is_admin}. Operation was done by admin with ID '{auth_user_id}'")
  return {"message": f"User with ID '{user_id}' now has is_admin={is_admin}"}
