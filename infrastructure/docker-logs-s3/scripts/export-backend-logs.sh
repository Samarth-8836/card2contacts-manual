#!/bin/bash

# Backend Docker logs export script
# Exports incremental logs from scanner_backend container to S3

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common-functions.sh"

# Configuration
SERVICE_NAME="backend"
CONTAINER_NAME="scanner_backend"
S3_PREFIX="prod/backend"
TEMP_DIR="/tmp/docker-logs-s3"

# Create temp directory
mkdir -p "${TEMP_DIR}"

# Get timestamps
LAST_TIMESTAMP=$(get_last_timestamp "${SERVICE_NAME}")
CURRENT_TIMESTAMP=$(get_current_timestamp)
FILENAME_TIMESTAMP=$(get_filename_timestamp)

# Define file paths
TEMP_LOG="${TEMP_DIR}/${SERVICE_NAME}-${FILENAME_TIMESTAMP}.log"
COMPRESSED_LOG="${TEMP_LOG}.gz"
S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/${SERVICE_NAME}-logs-${FILENAME_TIMESTAMP}.log.gz"

log_message "${SERVICE_NAME}" "Starting log export at ${CURRENT_TIMESTAMP}"
log_message "${SERVICE_NAME}" "Last export timestamp: ${LAST_TIMESTAMP:-N/A (first run)}"

# Get Docker logs incrementally
log_message "${SERVICE_NAME}" "Fetching logs from container ${CONTAINER_NAME}..."
if get_docker_logs "${CONTAINER_NAME}" "${LAST_TIMESTAMP}" > "${TEMP_LOG}"; then
    LOG_SIZE=$(wc -l < "${TEMP_LOG}")
    log_message "${SERVICE_NAME}" "Fetched ${LOG_SIZE} log lines"
else
    log_message "${SERVICE_NAME}" "Warning: Docker logs command returned non-zero exit code"
fi

# Check if we have any logs to export
if [[ -f "${TEMP_LOG}" ]] && [[ -s "${TEMP_LOG}" ]]; then
    # Compress the log file
    log_message "${SERVICE_NAME}" "Compressing log file..."
    if compress_log "${TEMP_LOG}" "${COMPRESSED_LOG}"; then
        ORIGINAL_SIZE=$(du -h "${TEMP_LOG}" | cut -f1)
        COMPRESSED_SIZE=$(du -h "${COMPRESSED_LOG}" | cut -f1)
        log_message "${SERVICE_NAME}" "Compressed: ${ORIGINAL_SIZE} → ${COMPRESSED_SIZE}"
    else
        log_message "${SERVICE_NAME}" "Error: Failed to compress log file"
        cleanup_temp_files "${TEMP_LOG}" "${COMPRESSED_LOG}"
        exit 1
    fi
    
    # Upload to S3
    log_message "${SERVICE_NAME}" "Uploading to S3: ${S3_PATH}"
    if upload_to_s3 "${COMPRESSED_LOG}" "${S3_PATH}" "${SERVICE_NAME}"; then
        # Update last timestamp only on successful upload
        update_last_timestamp "${SERVICE_NAME}" "${CURRENT_TIMESTAMP}"
        log_message "${SERVICE_NAME}" "Successfully completed export and updated timestamp"
        EXIT_CODE=0
    else
        log_message "${SERVICE_NAME}" "Error: Failed to upload to S3"
        EXIT_CODE=1
    fi
else
    # No logs in this interval, but still update timestamp
    update_last_timestamp "${SERVICE_NAME}" "${CURRENT_TIMESTAMP}"
    log_message "${SERVICE_NAME}" "No new logs in this interval. Timestamp updated."
    EXIT_CODE=0
fi

# Cleanup
cleanup_temp_files "${TEMP_LOG}" "${COMPRESSED_LOG}"
log_message "${SERVICE_NAME}" "Export completed with exit code ${EXIT_CODE}"

exit ${EXIT_CODE}
