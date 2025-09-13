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

### Usage

1.  **Create a GPX File:**
    Twists are the name used for GPX files in MotoTwist. These are intended to be single track files, but can contain multiple tracks as well. Routes are untested but should also work. Each Twist can be rated as a single unit, which is why it's best to keep them to one track each. You may get one of these files from a GPS device, or create one yourself:

    a)  **Create a route:**
        The first step to creating your GPX is to create a route on [Google Maps](https://www.google.ca/maps). This can have as many waypoints as are needed (but limited to 10 by Google) to trace the exact track you want.

    b)  **Convert to GPX:**
        A wonderful tool called [mapstogpx](https://mapstogpx.com/) can be used to convert a Google Maps link to a GPX file.

    c)  **Clean up GPX:**
        Next, [GPX Weaver](http://www.gpxweaver.com/) can be used to combine and edit as many GPX files as you want. At a minimum, you'll want to rename the track(s) and waypoints for display in MotoTwist. I highly recommend merging tracks if you bring in multiple GPX files.

> [!TIP]
> If you need more than 10 waypoints, you can create multiple GPX files and combine them! Just make sure the starts and ends of each connect so you have a seamless line.

2.  **Create a Twist:**
    Once you have your GPX file, you can create a Twist. Twists should be predominantly paved or unpaved. If they're a combination of both, select whichever was "the main attraction" of the Twist, as each type has different criteria they're rated on. If both segments are fun, consider splitting the Twist!

> [!TIP]
> If you upload the GPX first, the name of the file will be used to auto-populate the name field.

3.  **Rating Twists:**
    From the sidebar, you can now rate your Twist! There's a number of different criteria you can rate it on, and hovering over each will give a brief description.

> [!TIP]
> With some, but minimal, technical knowledge, the available criteria can be changed! Eventually this may be configurable via environment variables. See [#11](https://github.com/amot-dev/mototwist/issues/11).

4.  **General Use:**

    a) Twists can be shown and hidden. Clicking on a Twist will take you to it, as well as reveal rating information.

    b) Waypoints and tracks on the map can be clicked to show a description.

    c) Twists and ratings can be deleted (but not modified).

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

> [!TIP]
> If you want to modify criteria, make changes to `PavedRating` and/or `UnpavedRating` in `app/models.py` and run a migration.