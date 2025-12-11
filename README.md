Talk With Your Data is an AI-powered analytics platform that lets users query databases using natural language.
Instead of writing SQL manually, users can simply ask:

“Show monthly revenue trend for the last 6 months”
“Find customers with highest tax contributions”
“Detect anomalies in recent sales”

The system intelligently converts the question into safe SQL, executes it on SQLite, and returns:

Interactive charts (Line / Bar / Pie)

Dynamic tables

AI Smart Insights

Anomaly Detection

This replicates features of tools like Metabase, DataLens, and Power BI, but fully AI-driven.


Key Features
1. Natural Language to SQL

Uses local LLM (Ollama + Llama3.1) to convert English queries into SQL.

2. Secure SQL Generation

Auto-fix incorrect columns

Reject unsafe SQL (DROP, UPDATE, DELETE, etc.)

Strict schema rules

Automatic query cleaning

3. Smart Insight Engine

Analyzes data values and generates human-friendly insights:

“Revenue is significantly higher than average this month.”

“Drop detected in sales volume last week.”

4. Anomaly Detection

Detects spikes or sudden drops in data trends.

5. Multiple Visualizations

Line charts

Bar charts

Pie charts

Auto-detect chart type based on response

6. Modern Frontend

Built with React + Tailwind CSS

Clean UI

Dynamic tables

Insight & anomaly alert cards

7. Local LLM Execution (Private & Offline)

Uses Ollama

Supports models like:

llama3.1:8b

llama3.1:3b (faster)
