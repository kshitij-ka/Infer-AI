# Admin user management

## Why there is no self service registration

An open `/auth/register` endpoint is out of scope for this application's RBAC model. The assignment describes three roles, admin, user, and readonly, provisioned by an administrator, not self selected by whoever signs up. An open registration endpoint would also need email verification or an invite flow to be safe against abuse, which the assignment does not ask for.

## Creating the first admin

`scripts/seed_admin.py` creates exactly one admin user from the `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables. It refuses to run without both variables set, refuses a password under 8 characters, and refuses to create a user if the username already exists. Run it once per fresh database:

```bash
docker compose exec -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=changeme123 api \
  python -m scripts.seed_admin
```

## Creating every other user

`POST /admin/users`, restricted to the admin role via the existing `require_role` dependency, creates a user with a chosen username, password, and role. The response never includes the password or its hash. A duplicate username returns 409 rather than a generic 500, since a client submitting a form needs to distinguish "this username is taken" from "something went wrong."

A security review found that FastAPI's default handling of a request body validation failure echoes the submitted value back in the error response, which meant a password that failed the length check came back in plain text in the 422 body. `app/main.py` now has a global handler for this kind of error that strips the submitted value for the password field specifically, while leaving it in place for every other field, so a client can still see what value it sent for a field like username or role, just never for password.

## Password policy

The only password requirement enforced today is length, between 8 and 128 characters. There is no check against commonly used weak passwords. This is accepted for now because user creation is admin only, not public self service registration, which narrows the realistic threat to a careless administrator rather than an anonymous attacker probing a public signup form. A production deployment managing higher value accounts should add a check against a common password list before accepting a new password. 

## Concurrent seeding

`scripts/seed_admin.py` relies on the database's unique constraint on `username`, the same mechanism `POST /admin/users` uses, rather than only a check-then-insert query. This matters if the script is ever invoked more than once at the same time, for example by a retried CI/CD step or a restarted orchestration job: the first invocation to commit succeeds, and every other concurrent invocation gets the same clean "user already exists" message and exit code a sequential second run would produce, instead of an unhandled database error.

