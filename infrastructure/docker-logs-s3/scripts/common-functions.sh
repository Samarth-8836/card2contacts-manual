#!/bin/bash

# Common functions for Docker logs export to S3

S3_BUCKET="prod-app.card2contacts.com"
LOG_DIR="/var/log/docker-logs-s3"
TIMESTAMP_DIR="${LOG_DIR}/timestamps"
EXPORT_LOG="${LOG_DIR}/export.log"

# Create necessary directories
mkdir -p "${LOG_DIR}"
mkdir -p "${TIMESTAMP_DIR}"

# Function to log messages with timestamp
log_message() {
    local service=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${service}] ${message}" >> "${EXPORT_LOG}"
}

# Function to get current timestamp in UTC ISO format
get_current_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Function to get formatted filename timestamp
get_filename_timestamp() {
    date '+%Y-%m-%d_%H-%M-%S'
}

# Function to get last export timestamp
get_last_timestamp() {
    local service=$1
    local timestamp_file="${TIMESTAMP_DIR}/${service}.last"
    
    if [[ -f "${timestamp_file}" ]]; then
        cat "${timestamp_file}"
    else
        echo ""
    fi
}

# Function to update last export timestamp
update_last_timestamp() {
    local service=$1
    local timestamp=$2
    local timestamp_file="${TIMESTAMP_DIR}/${service}.last"
    echo "${timestamp}" > "${timestamp_file}"
}

# Function to compress log file with gzip
compress_log() {
    local input_file=$1
    local output_file=$2
    
    if [[ -f "${input_file}" ]]; then
        gzip -c "${input_file}" > "${output_file}"
        return $?
    else
        return 1
    fi
}

# Function to upload file to S3
upload_to_s3() {
    local local_file=$1
    local s3_path=$2
    local service=$3
    
    if [[ ! -f "${local_file}" ]]; then
        log_message "${service}" "Error: File ${local_file} does not exist"
        return 1
    fi
    
    if aws s3 cp "${local_file}" "${s3_path}" 2>&1; then
        log_message "${service}" "Successfully uploaded to ${s3_path}"
        return 0
    else
        log_message "${service}" "Failed to upload to ${s3_path}"
        return 1
    fi
}

# Function to get Docker logs with incremental filter
get_docker_logs() {
    local container_name=$1
    local last_timestamp=$2
    
    if [[ -z "${last_timestamp}" ]]; then
        # First run: get logs from last 5 minutes
        docker logs --since 5m --timestamps "${container_name}" 2>&1
    else
        # Incremental: get logs since last timestamp
        docker logs --since "${last_timestamp}" --timestamps "${container_name}" 2>&1
    fi
}

# Function to cleanup temporary files
cleanup_temp_files() {
    local temp_file=$1
    local compressed_file=$2
    
    [[ -f "${temp_file}" ]] && rm -f "${temp_file}"
    [[ -f "${compressed_file}" ]] && rm -f "${compressed_file}"
}
