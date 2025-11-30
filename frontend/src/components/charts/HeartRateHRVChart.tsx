import Plot from "react-plotly.js";
import type { HeartRateData, HRVData } from "@/types/health";

interface Props {
  heartRateData: HeartRateData[];
  hrvData: HRVData[];
}

export default function HeartRateHRVChart({ heartRateData, hrvData }: Props) {
  if (!heartRateData.length && !hrvData.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Heart Rate & HRV
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No heart rate data available
        </div>
      </div>
    );
  }

  const hrDates = heartRateData.map((d) => d.date);
  const hrvDates = hrvData.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Heart Rate & HRV
      </h3>
      <Plot
        data={[
          {
            x: hrDates,
            y: heartRateData.map((d) => d.resting_hr),
            type: "scatter",
            mode: "lines+markers",
            name: "Resting HR (bpm)",
            line: { color: "#dc3545" },
            marker: { size: 6 },
          },
          {
            x: hrvDates,
            y: hrvData.map((d) => d.hrv_avg),
            type: "scatter",
            mode: "lines+markers",
            name: "HRV (ms)",
            yaxis: "y2",
            line: { color: "#007bff" },
            marker: { size: 6 },
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 50, r: 50, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Heart Rate (bpm)" }, side: "left" },
          yaxis2: {
            title: { text: "HRV (ms)" },
            overlaying: "y",
            side: "right",
          },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
