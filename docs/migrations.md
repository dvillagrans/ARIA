# Database Migrations

Migrations live in `supabase/migrations/` and are applied with the Supabase
CLI (`supabase db reset` replays them from scratch locally).

## Known numbering collision

Two migrations intentionally share the `0002_` prefix:

- `0002_conversations_project.sql`
- `0002_project_info.sql`

**Do not rename these files.** They are already applied to existing
environments; renaming would make the Supabase CLI re-run or mis-track them.
Because of the collision, no new migration should reuse the `0002_` prefix —
number new migrations from the highest existing prefix (`0006_…` at the time
of writing) onward.

## Seeding the initial user

Migrations do **not** create any user: `0001_schema.sql` intentionally
contains no seed data with credentials. After `supabase db reset`, create
your user with `supabase/seed_initial_user.sql`, which takes
`SEED_USER_EMAIL` and `SEED_USER_PASSWORD` from the environment and refuses
unset, empty, or weak values (requires psql 15+):

```bash
export SEED_USER_EMAIL="you@example.com"
export SEED_USER_PASSWORD="<a strong password>"
psql "$SUPABASE_DB_URL" -X -f supabase/seed_initial_user.sql
```
