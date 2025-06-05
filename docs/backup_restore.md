# Database Backup and Restore

This document provides guidance on how to backup and restore the GraphRAG database, ensuring your data is safely preserved.

## Backup Scripts

The GraphRAG system includes three scripts for database backups:

### 1. Manual Backup (`backup_db.sh`)

This script creates a compressed backup of the PostgreSQL database with a timestamp.

```bash
# Create a backup
./scripts/backup_db.sh [backup_directory]
```

- `backup_directory`: Optional. Directory to store backups (default: `./backups`)

The script automatically detects whether the database is running in Docker or directly on the host and creates a timestamped backup like: `graphrag_backup_20230101_120000.sql.gz`

### 2. Restore Backup (`restore_db.sh`)

This script restores a database from a previously created backup.

```bash
# Restore from a backup
./scripts/restore_db.sh path/to/backup_file.sql.gz
```

- The script supports both compressed (`.sql.gz`) and uncompressed (`.sql`) backup files
- When restoring, it will prompt for confirmation before overwriting the existing database

### 3. Scheduled Backup (`scheduled_backup.sh`)

This script is designed to be run via cron to create regular backups with rotation.

```bash
# Create a scheduled backup
./scripts/scheduled_backup.sh [backup_directory] [retention_count]
```

- `backup_directory`: Optional. Directory to store backups (default: `./backups`)
- `retention_count`: Optional. Number of backups to keep (default: 7)

#### Setting up a Cron Job

To schedule automatic backups, add an entry to your crontab:

```bash
# Edit your crontab
crontab -e

# Add a line to run daily at 2:00 AM
0 2 * * * /full/path/to/graphrag/scripts/scheduled_backup.sh /full/path/to/backup/directory 7
```

## Best Practices

1. **Regular Backups**: Set up scheduled backups to run daily or weekly
2. **Offsite Storage**: Copy backups to an external location or cloud storage
3. **Test Restores**: Periodically test the restore process to ensure backups are valid
4. **Documentation**: Keep track of when backups are created and where they are stored

## Backup Contents

The backups include:

- All database tables and data
- Query cache and memory data
- User feedback and conversation threads
- Document chunks and embeddings

## Troubleshooting

If you encounter any issues with backups or restores:

1. **Check Permissions**: Ensure the scripts have execute permissions (`chmod +x script.sh`)
2. **Database Connection**: Verify the database connection details in the script match your setup
3. **Space Issues**: Ensure there's enough disk space for backups
4. **PostgreSQL Tools**: Make sure `pg_dump` and `psql` are available on your system or in the Docker container

For further assistance, consult the PostgreSQL documentation or open an issue on the project repository.