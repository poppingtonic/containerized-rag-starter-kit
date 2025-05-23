FROM ankane/pgvector:v0.5.1

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY add_cache_table.sql /docker-entrypoint-initdb.d/02-add_cache_table.sql
COPY add_feedback_table.sql /docker-entrypoint-initdb.d/03-add_feedback_table.sql
COPY add_ragas_scores.sql /docker-entrypoint-initdb.d/04-add_ragas_scores.sql