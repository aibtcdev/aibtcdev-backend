# Supabase Deployments

This guide explains how to set up automated Supabase database migrations using GitHub Actions when deploying new releases.

## Overview

When you create a new tag (e.g., `v1.0.0`), the system will automatically:

1. 🚀 Deploy your application via the existing `docker-image-deploy.yml` workflow
2. 🗄️ Deploy database migrations via the new `deploy-supabase-migrations.yml` workflow

## GitHub Secrets Setup

To enable automated Supabase deployments, you need to configure the following secrets in your GitHub repository:

### Required Secrets

Navigate to **Settings** → **Secrets and variables** → **Actions** in your GitHub repository and add:

#### `SUPABASE_ACCESS_TOKEN`
- **What**: Your Supabase personal access token
- **How to get**: 
  1. Go to [Supabase Access Tokens](https://supabase.com/dashboard/account/tokens)
  2. Click "Generate new token"
  3. Copy the token value
- **Permissions**: Must have access to your production project

#### `SUPABASE_DB_URL_PRODUCTION`
- **What**: Database connection string for production
- **How to get**:
  1. Go to your Supabase project dashboard
  2. Navigate to **Settings** → **Database**
  3. Copy the "Transaction pooler" connection string
  4. Format: `postgresql://postgres.xxx:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`

#### `SUPABASE_DB_URL_STAGING` (Optional)
- **What**: Database connection string for staging environment
- **When**: Only needed if you want to deploy pre-release tags (e.g., `v1.0.0-beta.1`) to staging
- **How to get**: Same as production, but from your staging Supabase project

## Deployment Flow

### Production Deployments

When you create a release tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

**What happens:**
1. ✅ `docker-image-deploy.yml` builds and pushes the Docker image
2. ✅ `deploy-supabase-migrations.yml` deploys database migrations to production
3. ✅ Application gets deployed to DigitalOcean (existing workflow)

### Staging Deployments (Pre-release)

For pre-release versions:

```bash
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

**What happens:**
1. ✅ Docker image gets built and pushed
2. ✅ Database migrations deploy to **staging** environment (if `SUPABASE_DB_URL_STAGING` is configured)
3. ❌ Application does **not** deploy to production (existing workflow skips pre-release tags)

## Migration Workflow Features

### 🔍 **Validation**
- Checks if migrations directory exists
- Counts migration files
- Skips deployment if no migrations found

### 🛡️ **Safety**
- Only runs if required secrets are configured
- Uses official [Supabase CLI action](https://github.com/supabase/setup-cli)
- Validates migration files before applying

### 📊 **Logging** 
- Detailed deployment logs
- Migration count reporting
- Deployment summary with tag, commit, and timestamp

### 🔄 **Environment Handling**
- **Production**: All release tags (`v1.0.0`, `v2.1.3`)
- **Staging**: Pre-release tags (`v1.0.0-beta.1`, `v1.0.0-rc.1`)

## Local Development

Your local Supabase setup remains unchanged:

```bash
# Local development
supabase start                    # Start local database
supabase migration new my_feature # Create new migration
supabase migration up            # Apply locally

# When ready to deploy
git add supabase/migrations/
git commit -m "Add new feature migration"
git tag v1.1.0
git push origin v1.1.0          # 🚀 Triggers automated deployment
```

## Troubleshooting

### Missing Secrets Error
```
Error: Required secrets not found
```
**Solution**: Ensure `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_URL_PRODUCTION` are configured in GitHub repository secrets.

### Migration Failed
```
Error: Migration failed to apply
```
**Solution**: 
1. Check the GitHub Actions logs for specific error details
2. Test the migration locally first: `supabase migration up`
3. Verify the database connection string is correct

### Workflow Skipped
```
Workflow was skipped
```
**Solution**: This is normal if:
- No migration files exist
- Required secrets are not configured
- Tag doesn't match the pattern (`v*`)

## Best Practices

1. **Test Locally First**: Always test migrations with `supabase migration up` before tagging
2. **Use Semantic Versioning**: Follow `v1.0.0` format for production releases
3. **Pre-release Testing**: Use `v1.0.0-beta.1` format for staging deployments
4. **Migration Naming**: Use descriptive names like `add_veto_table.sql`
5. **Backup First**: Ensure your production database is backed up before major migrations

## Related Files

- `.github/workflows/deploy-supabase-migrations.yml` - The migration deployment workflow
- `.github/workflows/docker-image-deploy.yml` - The application deployment workflow  
- `supabase/migrations/` - Your database migration files
- `supabase/config.toml` - Supabase project configuration