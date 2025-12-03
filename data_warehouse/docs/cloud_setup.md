# Cloud Services Setup Guide
# 云服务账户准备指南

This document provides step-by-step instructions for setting up cloud service accounts required for the Shanghai Transport Card data warehouse project.

## Overview

The following cloud services are required:
1. **Supabase** - Operational database (PostgreSQL)
2. **Databricks** - Data warehouse (Delta Lake)
3. **dbt Cloud** - Data transformation and scheduling
4. **Airbyte Cloud** - Data synchronization
5. **Power BI Desktop** - Data visualization (desktop application)

## 1. Supabase Setup

### Account Creation
1. Visit https://supabase.com
2. Click "Start your project" or "Sign up"
3. Sign up using GitHub, Google, or email
4. Verify your email address if required

### Project Creation
1. After login, click "New Project"
2. Fill in project details:
   - **Organization**: Create new or select existing
   - **Name**: Enter project name (e.g., "shanghai-transport")
   - **Database Password**: Set a strong password (save this securely)
   - **Region**: Select closest region (e.g., "Southeast Asia (Singapore)")
   - **Pricing Plan**: Select "Free" plan
3. Click "Create new project"
4. Wait for project provisioning (2-3 minutes)

### Get Connection Information
1. Go to Project Settings (gear icon)
2. Navigate to "Database" section
3. Find "Connection string" section
4. Copy the following information:
   - **Host**: `db.xxxxx.supabase.co`
   - **Database name**: `postgres`
   - **Port**: `5432`
   - **User**: `postgres`
   - **Password**: The password you set during project creation
5. Navigate to "API" section
6. Copy the following:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon public key**: For API access (optional)

### Free Tier Limits
- **Database Size**: 500 MB
- **Bandwidth**: 2 GB/month
- **API Requests**: Unlimited (with rate limits)
- **Storage**: 1 GB
- **Projects**: Unlimited

### Next Steps
- Save connection information securely
- Configure environment variables (see configuration files)
- Test connection using psql or Supabase Dashboard SQL Editor

## 2. Databricks Setup

### Account Creation
1. Visit https://databricks.com
2. Click "Try Databricks" or "Get Started"
3. Choose "Try Databricks Free" (14-day trial)
4. Fill in registration form:
   - Email address
   - Company name
   - Use case
5. Verify your email address
6. Complete account setup

### Workspace Creation
1. After login, you'll be prompted to create a workspace
2. Fill in workspace details:
   - **Workspace Name**: Enter name (e.g., "shanghai-transport-dw")
   - **Cloud Provider**: Select AWS, Azure, or GCP
   - **Region**: Select closest region
3. Click "Create Workspace"
4. Wait for workspace provisioning

### Create Compute Cluster
1. In Databricks workspace, click "Compute" in sidebar
2. Click "Create Cluster"
3. Configure cluster:
   - **Cluster Name**: e.g., "dev-cluster"
   - **Cluster Mode**: Select "Single Node" (for development)
   - **Databricks Runtime Version**: Select latest LTS (e.g., "13.3 LTS")
   - **Node Type**: Select smallest available (e.g., "i3.xlarge")
   - **Auto Termination**: Set to 30 minutes (to save credits)
   - **Enable autoscaling**: Uncheck (for single node)
4. Click "Create Cluster"
5. Wait for cluster to start

### Get Access Token
1. Click on your username (top right)
2. Select "User Settings"
3. Navigate to "Access Tokens" tab
4. Click "Generate New Token"
5. Enter token description (e.g., "dbt-access")
6. Set expiration (recommend 90 days)
7. Click "Generate"
8. **IMPORTANT**: Copy the token immediately (it won't be shown again)
9. Save token securely

### Get SQL Warehouse Information (for Power BI)
1. Click "SQL Warehouses" in sidebar
2. Click "Create SQL Warehouse"
3. Configure:
   - **Name**: e.g., "powerbi-warehouse"
   - **Cluster Size**: Select "2X-Small" (for free tier)
   - **Auto Stop**: Set to 10 minutes
4. Click "Create"
5. After creation, click on the warehouse
6. Copy the following information:
   - **Server Hostname**: `xxxxx.cloud.databricks.com`
   - **HTTP Path**: `/sql/1.0/warehouses/xxxxx`
   - **Port**: `443`

### Free Tier Limits
- **Trial Period**: 14 days
- **Compute Credits**: Limited credits during trial
- **After Trial**: Can use Community Edition (limited features)

### Next Steps
- Save all connection information securely
- Configure environment variables
- Test connection using Databricks SQL Editor

## 3. dbt Cloud Setup

### Account Creation
1. Visit https://cloud.getdbt.com
2. Click "Sign Up" or "Get Started"
3. Sign up using GitHub, Google, or email
4. Verify your email address

### Connect Repository
1. After login, you'll be prompted to connect a repository
2. Choose your Git provider (GitHub, GitLab, Bitbucket)
3. Authorize dbt Cloud to access your repositories
4. Select the repository containing your dbt project
5. Click "Continue"

### Create Project
1. Fill in project details:
   - **Project Name**: e.g., "Shanghai Transport DW"
   - **Repository**: Select your repository
   - **Branch**: Select branch (usually "main" or "master")
   - **dbt Version**: Select latest version (e.g., "1.7.0")
2. Click "Create Project"

### Configure Connection
1. Go to "Settings" > "Connections"
2. Click "New Connection"
3. Select "Databricks"
4. Fill in connection details:
   - **Connection Name**: e.g., "databricks-dev"
   - **Server Hostname**: From Databricks setup
   - **HTTP Path**: From Databricks SQL Warehouse
   - **Token**: From Databricks access token
   - **Catalog**: `hive_metastore` (default)
   - **Schema**: `shanghai_transport` (or your schema name)
5. Click "Test Connection"
6. If successful, click "Save"

### Create Environment
1. Go to "Settings" > "Environments"
2. Click "New Environment"
3. Fill in details:
   - **Name**: e.g., "Development"
   - **dbt Version**: Select version
   - **Connection**: Select the Databricks connection
4. Click "Create"

### Free Tier Limits
- **Developer Plan**: Free
  - 1 developer seat
  - 5,000 credits per month
  - Unlimited runs
  - Community support

### Next Steps
- Configure dbt project files
- Create jobs and schedules (covered in later steps)

## 4. Airbyte Cloud Setup

### Account Creation
1. Visit https://cloud.airbyte.com
2. Click "Sign Up" or "Get Started"
3. Sign up using email or Google
4. Verify your email address

### Create Workspace
1. After login, you'll be prompted to create a workspace
2. Fill in workspace details:
   - **Workspace Name**: e.g., "shanghai-transport"
   - **Company Name**: Your company name
3. Click "Create Workspace"

### Get API Credentials (Optional, for automation)
1. Go to "Settings" > "API"
2. Click "Generate API Key"
3. Copy the API key
4. Save securely

### Free Tier Limits
- **Free Plan**: Available with limitations
  - Limited sync frequency
  - Limited data volume
  - Community support

### Next Steps
- Configure sources and destinations (covered in later steps)
- Set up connections (covered in later steps)

## 5. Power BI Desktop Setup

### Download and Installation
1. Visit https://powerbi.microsoft.com/desktop/
2. Click "Download free"
3. Run the installer
4. Follow installation wizard
5. Launch Power BI Desktop

### Install Databricks ODBC Driver
1. Visit https://databricks.com/spark/odbc-driver-download
2. Download the appropriate driver for your OS
3. Run the installer
4. Follow installation wizard

### Free Tier
- **Power BI Desktop**: Completely free
- **Power BI Service**: Free tier available with limitations

### Next Steps
- Configure Databricks connection (covered in later steps)
- Create reports (covered in later steps)

## Environment Variables Configuration

Create a `.env` file in the project root (do not commit to version control):

```bash
# Supabase Configuration
SUPABASE_API_KEY=your_supabase_api_key
SUPABASE_DB_PASSWORD=your_db_password
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_PROJECT_URL=https://xxxxx.supabase.co

# Databricks Configuration
DATABRICKS_TOKEN=your_databricks_token
DATABRICKS_SERVER_HOSTNAME=xxxxx.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxx
DATABRICKS_CLUSTER_ID=xxxxx-xxxxx-xxxxx

# Airbyte Configuration (Optional)
AIRBYTE_API_KEY=your_airbyte_api_key
AIRBYTE_WORKSPACE_ID=your_workspace_id
```

## Security Best Practices

1. **Never commit credentials**: Use environment variables or secret management
2. **Rotate tokens regularly**: Update access tokens every 90 days
3. **Use least privilege**: Grant minimum necessary permissions
4. **Enable MFA**: Enable multi-factor authentication where available
5. **Monitor usage**: Regularly check usage and costs
6. **Backup credentials**: Store credentials securely (password manager)

## Troubleshooting

### Supabase Connection Issues
- Verify database password is correct
- Check if IP is whitelisted (if using IP restrictions)
- Ensure database is running (check project status)

### Databricks Connection Issues
- Verify token hasn't expired
- Check cluster/SQL warehouse is running
- Verify HTTP path is correct

### dbt Cloud Connection Issues
- Verify Databricks connection details
- Check dbt version compatibility
- Ensure repository is accessible

## Cost Estimation

### Free Tier Summary
- **Supabase**: Free (500 MB database)
- **Databricks**: 14-day free trial, then Community Edition
- **dbt Cloud**: Free Developer plan
- **Airbyte**: Free plan with limitations
- **Power BI Desktop**: Free

### Estimated Monthly Cost (After Free Tier)
- **Supabase**: $0 (if within free limits)
- **Databricks**: $0 (Community Edition) or ~$100+ (if using paid tier)
- **dbt Cloud**: $0 (Developer plan)
- **Airbyte**: $0 (if within free limits)
- **Power BI**: $0 (Desktop) or $10/user/month (Service)

## Next Steps

After completing all account setups:
1. Save all connection information securely
2. Configure environment variables
3. Proceed to Step 2: Supabase Configuration and Table Creation


