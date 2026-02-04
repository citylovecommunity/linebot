#build image

#試跑form_app
docker container run --rm --env-file .env ctlove_app gunicorn -b 0.0.0.0:8080 form_app.app:app 


#debug
docker container run --rm --env-file .env -p 5678:5678 -it ctlove_app bash