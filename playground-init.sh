set -e
if [ ! -d "playground" ]
then
    exit 1
fi
cd playground
export ZRB_SHOW_PROMPT=0
export ZRB_SHOW_TIME=0