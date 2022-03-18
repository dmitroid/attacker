#bash
count=$1
if [ -z "$count" ]; then
  count=15
fi
docker-compose up --build -d --scale app=$count
