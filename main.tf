terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.0.0"
    }
  }

  required_version = ">= 1.3.0"
}

provider "google" {
  project = "quiz-app-457308"  # 🔁 Thay bằng project ID thật
  region  = "asia-southeast1"      # 🌏 Có thể đổi sang us-central1, asia-east1, v.v.
}

resource "google_cloud_run_service" "quiz_app" {
  name     = "quiz-app"
  location = "asia-southeast1"

  template {
    spec {
      containers {
        image = "yuj1n/quiz-app:latest"

        ports {
          container_port = 5000
        }

        env {
          name  = "FLASK_ENV"
          value = "production"
        }
      }
    }
  }
}

# Public access (không cần auth để truy cập web)
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_service.quiz_app.name
  location = google_cloud_run_service.quiz_app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
