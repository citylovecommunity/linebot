#!/usr/bin/env bash
docker build -t dispatcher-image .


docker run --rm \
-e DISPATCHER_MODULE=$DISPATCHER_MODULE \
-e DB="${{ secrets.DB }}" \
-e LINE_CHANNEL_SECRET="${{ secrets.LINE_CHANNEL_SECRET }}" \
-e LINE_CHANNEL_ACCESS_TOKEN="${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}" \
-e TEST_USER_ID="${{ secrets.TEST_USER_ID }}" \
-e ADMIN_LINE_ID="${{ secrets.ADMIN_LINE_ID }}" \
-e FORM_WEB_URL="${{ secrets.FORM_WEB_URL }}" \
-e SENDER_PRODUCTION="${{ secrets.SENDER_PRODUCTION }}" \
dispatcher-image