Here's the Garmin API documentation. Please review it first before making any architectural decisions:

https://developer.garmin.com/gc-developer-program/overview/
https://developer.garmin.com/gc-developer-program/activity-api/
https://developer.garmin.com/gc-developer-program/health-api/
https://developer.garmin.com/gc-developer-program/training-api/

I'd like to build a separate project called **Running Data Analysis using the Garmin API**.

## Project Goal

The goal is to build a long-term personal running analytics platform powered by my Garmin data. I use a **Garmin Forerunner 170** to track:

* Running activities
* Daily health metrics
* Workouts
* Sleep
* Heart rate
* Recovery and other fitness metrics

I want to automatically sync new data from Garmin every day and store it in my own database. This project should treat Garmin as the data source while maintaining a historical dataset for long-term analysis, rather than relying solely on Garmin Connect.

## Vision

This is not just a dashboard.

I want to build an AI-powered running coach that can analyze my historical data, identify trends, and provide personalized recommendations.

For example, one of my goals is to complete a **10 km run in under 60 minutes**. The AI should use all available historical data to answer questions such as:

* Am I improving toward my goal?
* Which workouts contribute the most to my progress?
* What are my current strengths and weaknesses?
* Am I training too hard or not hard enough?
* Is my aerobic base improving?
* Is my recovery sufficient?
* Am I at risk of overtraining?
* What should my training focus be next week?
* Based on my historical performance, what pace should I target?

## Data Collection

I want to collect and store as much relevant data as possible, including but not limited to:

* Activities (running, walking, cycling, etc.)
* Splits and laps
* GPS routes
* Heart rate
* Cadence
* Pace
* Elevation
* Training load
* VO2 Max
* Recovery metrics
* Sleep
* Resting heart rate
* Body Battery
* Stress
* Training readiness (if available)
* Daily summaries
* Workout history

Please identify every useful Garmin API that should be integrated—not just the Activity API.

## Architecture

Before writing any code, I'd like you to:

1. Review the Garmin Developer documentation.
2. Identify which Garmin APIs and endpoints are relevant.
3. Propose a scalable architecture.
4. Design the database schema.
5. Explain the data ingestion pipeline.
6. Explain how the AI layer should consume the stored data.
7. Recommend technologies for storage, orchestration, visualization, and AI.

Please challenge my ideas if you think there are better approaches. My goal is to build a robust, extensible platform that I can continue using for many years as my personal running analytics and AI coaching system.
