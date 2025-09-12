# MotoTwists

A self-hosted, Dockerized service to store, rate, and view your favorite motorcycle roads from GPX files. 

## Getting Started

### Prerequisites

To get this application running, you will need to have **Docker** and **Docker Compose** installed on your system.

* **Docker:** [Installation Guide](https://docs.docker.com/get-docker/)
* **Docker Compose:** [Installation Guide](https://docs.docker.com/compose/install/)

### Installation

Follow these steps to set up and run the application.

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:amot-dev/MotoTwist.git
    cd MotoTwist
    ```

2.  **Configure environment variables:**
    Find `.env.example` in the project's root directory. Copy this into your own `.env` file.

3.  **Remove the development compose file:**
    This file overrides some options in `docker-compose.yml` and is not needed except for development.
    ```bash
    rm docker-compose.override.yml
    ```

3.  **Build and run the containers:**
    Use Docker Compose to build the image and start the services. The `-d` flag runs the containers in detached mode.
    ```bash
    docker compose up -d --build
    ```

4.  **Access the application:**
    Open your web browser and navigate to `http://localhost:8000`.