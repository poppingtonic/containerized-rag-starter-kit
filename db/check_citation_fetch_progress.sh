#!/bin/bash

# Check citation fetch progress
# call this first: watch -n 10 curl -X POST http://localhost:8001/citations/citations/fetch?admin=true
# then call this with watch -n 12 ./check_citation_fetch_progress.sh
docker compose exec db-ilri psql -U ilri_user -d digest_api_ilri -c "
  SELECT                                        
      CASE                                      
          WHEN citation_fetched = TRUE AND reference IS NOT NULL THEN 1                           
          WHEN citation_fetch_attempted_at IS NOT NULL THEN -1                                     
          ELSE 0                  
      END as status,                            
      COUNT(*) as count                         
  FROM document                                 
  GROUP BY 1                                    
  ORDER BY count DESC;"