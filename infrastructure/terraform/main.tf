# Terraform configuration for DocuScan infrastructure
# Alternative to shell script deployment

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "db_password" {
  description = "Database root password"
  type        = string
  sensitive   = true
}

# Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "redis.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])
  
  service            = each.value
  disable_on_destroy = false
}

# Cloud Storage Buckets
resource "google_storage_bucket" "uploads" {
  name     = "docuscan-uploads-${var.project_id}"
  location = var.region
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "results" {
  name     = "docuscan-results-${var.project_id}"
  location = var.region
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# Pub/Sub Topic and Subscription
resource "google_pubsub_topic" "ocr_jobs" {
  name = "ocr-jobs"
}

resource "google_pubsub_subscription" "ocr_jobs_sub" {
  name  = "ocr-jobs-sub"
  topic = google_pubsub_topic.ocr_jobs.name
  
  ack_deadline_seconds = 600
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Cloud SQL Instance
resource "google_sql_database_instance" "docuscan_db" {
  name             = "docuscan-db"
  database_version = "POSTGRES_15"
  region           = var.region
  
  settings {
    tier = "db-f1-micro"
    
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "all"
        value = "0.0.0.0/0"
      }
    }
    
    backup_configuration {
      enabled = true
      start_time = "03:00"
    }
  }
  
  deletion_protection = false
}

resource "google_sql_database" "docuscan" {
  name     = "docuscan"
  instance = google_sql_database_instance.docuscan_db.name
}

resource "google_sql_user" "postgres" {
  name     = "postgres"
  instance = google_sql_database_instance.docuscan_db.name
  password = var.db_password
}

# Memorystore Redis Instance
resource "google_redis_instance" "cache" {
  name           = "docuscan-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  
  redis_version = "REDIS_7_0"
}

# Cloud Run API Service
resource "google_cloud_run_service" "api" {
  name     = "docuscan-api"
  location = var.region
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/docuscan-api:latest"
        
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        
        env {
          name  = "DB_HOST"
          value = google_sql_database_instance.docuscan_db.private_ip_address
        }
        
        env {
          name  = "REDIS_HOST"
          value = google_redis_instance.cache.host
        }
        
        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }
    
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"      = "10"
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.docuscan_db.connection_name
      }
    }
  }
  
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Allow unauthenticated access to API
resource "google_cloud_run_service_iam_member" "api_noauth" {
  service  = google_cloud_run_service.api.name
  location = google_cloud_run_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "api_url" {
  value = google_cloud_run_service.api.status[0].url
}

output "db_connection_name" {
  value = google_sql_database_instance.docuscan_db.connection_name
}

output "redis_host" {
  value = google_redis_instance.cache.host
}

output "upload_bucket" {
  value = google_storage_bucket.uploads.name
}

output "results_bucket" {
  value = google_storage_bucket.results.name
}
