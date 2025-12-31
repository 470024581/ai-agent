#!/bin/bash
# Simple script to register Debezium connector
# 注册 Debezium connector 的简单脚本

CONNECTOR_NAME="postgres-transport-cdc"
CONNECT_URL="http://localhost:8083"
CONFIG_FILE="../debezium/postgres.json"

echo "Registering Debezium connector: $CONNECTOR_NAME"

# Check if connector exists
if curl -s "$CONNECT_URL/connectors/$CONNECTOR_NAME" > /dev/null; then
    echo "Connector already exists. Updating..."
    curl -X PUT "$CONNECT_URL/connectors/$CONNECTOR_NAME/config" \
        -H "Content-Type: application/json" \
        -d @"$CONFIG_FILE" | jq .
else
    echo "Creating new connector..."
    curl -X POST "$CONNECT_URL/connectors" \
        -H "Content-Type: application/json" \
        -d @"$CONFIG_FILE" | jq .
fi

echo ""
echo "Connector status:"
curl -s "$CONNECT_URL/connectors/$CONNECTOR_NAME/status" | jq .


