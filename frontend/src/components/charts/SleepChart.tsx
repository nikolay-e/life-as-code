import Plot from "react-plotly.js";
import type { SleepData } from "@/types/health";

interface Props {
  data: SleepData[];
}

export default function SleepChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Sleep Analysis
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No sleep data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);
  const toHours = (minutes: number | null) => (minutes ? minutes / 60 : null);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Sleep Analysis
      </h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => toHours(d.total_sleep_minutes)),
            type: "scatter",
            mode: "lines+markers",
            name: "Total Sleep (hrs)",
            line: { color: "#001f3f" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => d.sleep_score),
            type: "scatter",
            mode: "lines+markers",
            name: "Sleep Score",
            yaxis: "y2",
            line: { color: "#007bff" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => toHours(d.deep_minutes)),
            type: "bar",
            name: "Deep (hrs)",
            marker: { color: "#001f3f" },
            visible: "legendonly",
          },
          {
            x: dates,
            y: data.map((d) => toHours(d.light_minutes)),
            type: "bar",
            name: "Light (hrs)",
            marker: { color: "#7FDBFF" },
            visible: "legendonly",
          },
          {
            x: dates,
            y: data.map((d) => toHours(d.rem_minutes)),
            type: "bar",
            name: "REM (hrs)",
            marker: { color: "#B10DC9" },
            visible: "legendonly",
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 50, r: 50, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          barmode: "stack",
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Hours" }, side: "left" },
          yaxis2: {
            title: { text: "Score" },
            overlaying: "y",
            side: "right",
            range: [0, 100],
          },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
