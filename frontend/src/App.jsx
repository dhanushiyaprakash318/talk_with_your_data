import React, { useState, useMemo } from "react";
import axios from "axios";
import { Line } from "react-chartjs-2";
import "chart.js/auto";
import { ReactMediaRecorder } from "react-media-recorder";

export default function App() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [cols, setCols] = useState([]);
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState("");
  const [insight, setInsight] = useState("");
  const [anomaly, setAnomaly] = useState("");

  // ---------- TEXT TO SPEECH ----------
  function speak(text) {
    if (!text) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-US";
    utter.rate = 1;
    utter.pitch = 1;
    window.speechSynthesis.speak(utter);
  }

  // ---------- ASK QUESTION ----------
  async function ask() {
    if (!q.trim()) return;

    setLoading(true);
    setMessage("");
    setInsight("");
    setAnomaly("");
    setCols([]);
    setRows([]);

    try {
      const resp = await axios.post(
        "http://localhost:8000/chat",
        { question: q },
        { timeout: 0 }
      );

      const data = resp.data;

      setCols(data.data?.columns || []);
      setRows(data.data?.rows || []);
      setMessage(data.message || "");
      setInsight(data.insight || "");
      setAnomaly(data.anomaly || "");

      // 🔊 AUTO SPEAK (ANOMALY FIRST)
      if (data.anomaly) {
        speak("Warning. " + data.anomaly);
      } else if (data.insight) {
        speak(data.insight);
      }

    } catch (err) {
      console.error(err);
      setMessage(err.response?.data?.detail || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  // ---------- SPEECH TO TEXT ----------
  async function sendAudio(audioBlob) {
    const formData = new FormData();
    formData.append("file", audioBlob, "audio.wav");

    try {
      const resp = await axios.post(
        "http://localhost:8000/speech_to_text",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      setQ(resp.data.text);
    } catch (err) {
      console.error("Speech error:", err);
    }
  }

  // ---------- TIME COLUMN ----------
  const timeColumn = useMemo(() => {
    if (!cols.length) return null;
    const lower = cols.map(c => c.toLowerCase());
    if (lower.includes("month")) return cols[lower.indexOf("month")];
    if (lower.includes("order_date")) return cols[lower.indexOf("order_date")];
    return null;
  }, [cols]);

  // ---------- NUMERIC COLUMN ----------
  const numericColumn = useMemo(() => {
    if (!cols.length || !rows.length) return null;

    if (cols.includes("tax")) return "tax";
    if (cols.includes("discount")) return "discount";
    if (cols.includes("quantity")) return "quantity";
    if (cols.includes("revenue")) return "revenue";
    if (cols.includes("amount")) return "amount";

    for (const c of cols) {
      if (c === timeColumn) continue;
      if (!isNaN(Number(rows[0][c]))) return c;
    }
    return null;
  }, [cols, rows, timeColumn]);

  // ---------- CHART DATA ----------
  const chartData = useMemo(() => {
    if (!timeColumn || !numericColumn) return null;
    return {
      labels: rows.map(r => r[timeColumn]),
      datasets: [
        {
          label: numericColumn,
          data: rows.map(r => Number(r[numericColumn])),
          borderColor: "rgb(75, 192, 192)",
          tension: 0.3,
        },
      ],
    };
  }, [rows, timeColumn, numericColumn]);

  return (
    <div className="min-h-screen p-6 bg-gray-100">
      <div className="max-w-5xl mx-auto bg-white rounded-xl shadow p-6 grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* INPUT PANEL */}
        <div className="md:col-span-2">
          <h1 className="text-2xl font-semibold mb-2">Analytics Chatbot</h1>

          <textarea
            value={q}
            onChange={(e) => setQ(e.target.value)}
            rows={3}
            className="w-full border p-3 rounded"
            placeholder="Ask something like: Show monthly revenue trend for last 6 months"
          />

          <div className="mt-3 flex gap-2">
            <button
              onClick={ask}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded"
            >
              {loading ? "Thinking..." : "Ask"}
            </button>

            <button
              onClick={() => setQ("Show monthly revenue trend for last 6 months")}
              className="px-4 py-2 border rounded"
            >
              Example
            </button>

            <ReactMediaRecorder
              audio
              onStop={(blobUrl, blob) => sendAudio(blob)}
              render={({ startRecording, stopRecording }) => (
                <button
                  className="px-4 py-2 bg-purple-600 text-white rounded"
                  onMouseDown={startRecording}
                  onMouseUp={stopRecording}
                >
                  🎤 Hold to Speak
                </button>
              )}
            />
          </div>

          {/* INSIGHT */}
          {insight && (
            <div className="mt-6 p-4 bg-blue-50 border-l-4 border-blue-600 rounded">
              <h4 className="font-semibold text-blue-800">📊 Insight</h4>
              <p className="text-blue-900 text-sm mt-1">{insight}</p>
              <button
                onClick={() => speak(insight)}
                className="mt-2 px-3 py-1 bg-green-600 text-white rounded"
              >
                🔊 Speak Insight
              </button>
            </div>
          )}

          {/* ANOMALY */}
          {anomaly && (
            <div className="mt-4 p-4 bg-red-100 border-l-4 border-red-600 rounded">
              <h4 className="font-semibold text-red-800">⚠️ Anomaly Detected</h4>
              <p className="text-red-900 text-sm mt-1">{anomaly}</p>
              <button
                onClick={() => speak("Warning. " + anomaly)}
                className="mt-2 px-3 py-1 bg-red-600 text-white rounded"
              >
                🔊 Speak Anomaly
              </button>
            </div>
          )}
        </div>

        {/* OUTPUT PANEL */}
        <div>
          <h3 className="font-medium">Result</h3>
          <p className="text-sm text-gray-600">{message}</p>

          {chartData && <Line data={chartData} />}

          <div className="table-wrap mt-4 overflow-auto max-h-96">
            <table className="w-full text-sm border">
              <thead>
                <tr>
                  {cols.map(c => (
                    <th key={c} className="p-2 border-b">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    {cols.map(c => (
                      <td key={c} className="p-2 border-b">{String(r[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
