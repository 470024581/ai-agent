# Supabase Setup Guide
# Supabase 设置指南

This guide walks you through setting up Supabase for the Shanghai Transport Card data warehouse project.

## Prerequisites

- A web browser
- An email address for account creation
- Basic understanding of SQL (helpful but not required)

## Step 1: Create Supabase Account

1. Visit https://supabase.com
2. Click **"Start your project"** or **"Sign up"** button
3. Choose a sign-up method:
   - **GitHub** (recommended for developers)
   - **Google**
   - **Email** (enter email and password)
4. Complete the sign-up process
5. Verify your email address if required

## Step 2: Create a New Project

1. After logging in, you'll see the Supabase dashboard
2. Click **"New Project"** button (usually in the top right)
3. Fill in the project details:
   - **Organization**: 
     - If you don't have one, click "Create new organization"
     - Enter organization name (e.g., "My Company")
     - Click "Create organization"
   - **Name**: Enter project name (e.g., "shanghai-transport")
   - **Database Password**: 
     - Set a strong password (minimum 8 characters)
     - **IMPORTANT**: Save this password securely - you'll need it for database connections
     - Consider using a password manager
   - **Region**: Select the closest region to your location
     - Options include: US West, US East, EU West, EU Central, Asia Pacific (Singapore), etc.
     - For Shanghai, select **"Southeast Asia (Singapore)"** or **"Asia Pacific"**
   - **Pricing Plan**: Select **"Free"** plan
4. Click **"Create new project"**
5. Wait for project provisioning (usually 2-3 minutes)
   - You'll see a progress indicator
   - Don't close the browser during this process

## Step 3: Get Connection Information

After your project is created, you need to collect connection information:

### Database Connection Information

1. In the Supabase dashboard, click the **gear icon** (⚙️) in the left sidebar (Settings)
2. Navigate to **"Database"** section
3. Scroll down to **"Connection string"** section
4. You'll see different connection string formats. For our project, we need:
   - **Host**: Found in the connection string (format: `db.xxxxx.supabase.co`)
   - **Database name**: Usually `postgres`
   - **Port**: Usually `5432`
   - **User**: Usually `postgres`
   - **Password**: The password you set during project creation

5. Copy these values and save them securely

### API Keys

1. Still in Settings, navigate to **"API"** section
2. You'll see:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon public key**: A long string starting with `eyJ...`
   - **service_role key**: Another long string (keep this secret!)
3. Copy the **Project URL** and **anon public key**
4. **IMPORTANT**: Never expose the service_role key publicly

## Step 4: Configure Environment Variables

1. In your project root directory, create a `.env` file (if it doesn't exist)
2. Add the following variables:

```bash
# Supabase Configuration
SUPABASE_PROJECT_URL=https://xxxxx.supabase.co
SUPABASE_API_KEY=your_anon_public_key_here
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_DB_PASSWORD=your_database_password_here
```

3. Replace the placeholder values with your actual values
4. **IMPORTANT**: Add `.env` to `.gitignore` to prevent committing secrets

## Step 5: Test Database Connection

### Option 1: Using Supabase SQL Editor

1. In Supabase dashboard, click **"SQL Editor"** in the left sidebar
2. Click **"New query"**
3. Run a test query:
```sql
SELECT version();
```
4. You should see PostgreSQL version information

### Option 2: Using psql (Command Line)

If you have PostgreSQL client installed:

```bash
psql "postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres"
```

Replace `YOUR_PASSWORD` and `xxxxx` with your actual values.

### Option 3: Using Python Script

Create a test script `test_connection.py`:

```python
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('SUPABASE_DB_HOST'),
        port=5432,
        database='postgres',
        user='postgres',
        password=os.getenv('SUPABASE_DB_PASSWORD')
    )
    print("Connection successful!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
```

Run: `python test_connection.py`

## Step 6: Verify Project Status

1. In Supabase dashboard, check the project status
2. Ensure all services are running (green indicators):
   - Database
   - API
   - Storage
   - Auth

## Free Tier Limits

Be aware of Supabase free tier limitations:

- **Database Size**: 500 MB
- **Bandwidth**: 2 GB/month
- **API Requests**: Unlimited (with rate limits)
- **Storage**: 1 GB
- **Projects**: Unlimited
- **Database Backups**: 7 days retention

## Troubleshooting

### Project Creation Fails

- Check your internet connection
- Try a different region
- Wait a few minutes and try again
- Contact Supabase support if issue persists

### Cannot Connect to Database

- Verify the password is correct
- Check if the project is still provisioning (wait a few minutes)
- Verify the host address is correct
- Check if your IP is blocked (unlikely on free tier)

### Forgot Database Password

- Go to Settings > Database
- Click "Reset database password"
- Set a new password
- Update your `.env` file

### Connection Timeout

- Check your internet connection
- Verify the region you selected is accessible
- Try using Supabase SQL Editor instead

## Security Best Practices

1. **Never commit `.env` file**: Add it to `.gitignore`
2. **Use environment variables**: Don't hardcode credentials
3. **Rotate passwords regularly**: Change database password periodically
4. **Use anon key for client-side**: Only use service_role key server-side
5. **Enable Row Level Security (RLS)**: For production applications

## Next Steps

After completing Supabase setup:

1. ✅ Save all connection information securely
2. ✅ Configure environment variables
3. ✅ Test database connection
4. ➡️ Proceed to **Step 2: Create Database Tables** (see `create_supabase_tables.md`)

## Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase SQL Editor Guide](https://supabase.com/docs/guides/database/overview)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Support

If you encounter issues:
- Check [Supabase Status Page](https://status.supabase.com/)
- Visit [Supabase Discord](https://discord.supabase.com/)
- Review [Supabase GitHub Discussions](https://github.com/supabase/supabase/discussions)


