# MotoTwist

A self-hosted, Dockerized service to store, rate, and view your favorite motorcycle roads from GPX files.


## Getting Started

### Prerequisites

To get this application running, you will need to have **Docker** and **Docker Compose** installed on your system.

* **Docker:** [Installation Guide](https://docs.docker.com/get-docker/)
* **Docker Compose:** [Installation Guide](https://docs.docker.com/compose/install/)

### Installation

1.  **Download the latest compose file:** 
    Place 
    [`docker-compose.yml`](https://github.com/amot-dev/mototwist/blob/master/docker-compose.yml) in its own directory.

2.  **Configure environment variables:**
    Using [`.env.example`](https://github.com/amot-dev/mototwist/blob/master/.env.example) as a starting point, configure your desired environment variables. These should be placed in a `.env` file in the same directory as your `docker-compose.yml` file.

3.  **Run the containers:**
    From the directory containing your `docker-compose.yml`, run:
    ```bash
    docker compose up -d
    ```

4.  **Access the application:**
    Open your web browser and navigate to `http://localhost:8000`.

## Developing

Follow these steps to set up and run the application in development mode.

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:amot-dev/MotoTwist.git
    cd MotoTwist
    ```

2.  **Configure environment variables:**
    Find `.env.example` in the project's root directory. Copy this into your own `.env` file. Uncomment the developer options.

3.  **Build and run the containers:**
    Use Docker Compose to build the image and start the services. A handy `build.sh` script exists that does just this, as well as a few other things.

4.  **Access the application:**
    Open your web browser and navigate to `http://localhost:8000`.

5.  **Start Developing:**
    More thorough documentation for this is coming (maybe), but I'm sure you can figure it out.

6.  **Migrate the database if needed:**
    If you make any model changes, you'll need to make a migration from them. All migrations are applied to the database on container restart.
    ```bash
    docker compose exec mototwist alembic revision --autogenerate -m "Your very descriptive message"
    ```
