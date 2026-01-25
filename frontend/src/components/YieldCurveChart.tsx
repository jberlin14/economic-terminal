import React from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, ComposedChart } from 'recharts';

interface YieldCurve {
  timestamp: string;
  curve: {
    '1M': number | null;
    '3M': number | null;
    '6M': number | null;
    '1Y': number | null;
    '2Y': number | null;
    '5Y': number | null;
    '10Y': number | null;
    '20Y': number | null;
    '30Y': number | null;
  };
  spreads: {
    '10Y-2Y': number | null;
    '10Y-3M': number | null;
    '30Y-10Y': number | null;
  };
}

interface YieldCurveChartProps {
  curve: YieldCurve | null;
}

export const YieldCurveChart: React.FC<YieldCurveChartProps> = ({ curve }) => {
  if (!curve || !curve.curve) {
    return (
      <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
        <h2 className="text-xl font-bold mb-4">📈 Treasury Yield Curve</h2>
        <div className="h-64 flex items-center justify-center text-terminal-text-dim">
          No yield curve data available
        </div>
      </div>
    );
  }

  const tenors = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y'];
  
  const chartData = tenors.map(tenor => ({
    tenor,
    yield: curve.curve[tenor as keyof typeof curve.curve] || 0
  })).filter(d => d.yield !== 0);

  const spread10y2y = curve.spreads['10Y-2Y'];
  const isInverted = spread10y2y !== null && spread10y2y < 0;
  const spreadBps = spread10y2y !== null ? (spread10y2y * 100).toFixed(0) : 'N/A';

  return (
    <div className="bg-terminal-panel rounded-lg border border-terminal-border p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <span>📈</span>
          <span>Treasury Yield Curve</span>
        </h2>
        
        {/* Spread Badge */}
        <div className={`px-4 py-2 rounded-lg ${
          isInverted 
            ? 'bg-critical/20 border border-critical text-critical' 
            : 'bg-positive/20 border border-positive text-positive'
        }`}>
          <span className="font-mono text-lg">
            10Y-2Y: {spreadBps} bps
            {isInverted && ' ⚠️'}
          </span>
        </div>
      </div>

      {/* Inversion Warning */}
      {isInverted && (
        <div className="mb-4 p-3 bg-critical/10 border border-critical rounded-lg text-critical text-sm">
          ⚠️ Yield curve is inverted - historically signals increased recession risk
        </div>
      )}

      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="yieldGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}/>
              </linearGradient>
            </defs>
            
            <XAxis 
              dataKey="tenor" 
              stroke="#8b92b0"
              tick={{ fill: '#8b92b0', fontSize: 12 }}
            />
            <YAxis 
              stroke="#8b92b0"
              tick={{ fill: '#8b92b0', fontSize: 12 }}
              tickFormatter={(value) => `${value.toFixed(1)}%`}
              domain={['auto', 'auto']}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1a1f2e', 
                border: '1px solid #2d3548',
                borderRadius: '8px'
              }}
              labelStyle={{ color: '#e6e8f0' }}
              formatter={(value: number) => [`${value.toFixed(3)}%`, 'Yield']}
            />
            
            <Area
              type="monotone"
              dataKey="yield"
              stroke="#60a5fa"
              strokeWidth={2}
              fill="url(#yieldGradient)"
            />
            <Line
              type="monotone"
              dataKey="yield"
              stroke="#60a5fa"
              strokeWidth={3}
              dot={{ fill: '#60a5fa', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: '#60a5fa' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Key Yields */}
      <div className="mt-4 grid grid-cols-4 gap-4">
        <div className="text-center">
          <div className="text-terminal-text-dim text-xs">3M</div>
          <div className="font-mono text-lg">{curve.curve['3M']?.toFixed(2) || 'N/A'}%</div>
        </div>
        <div className="text-center">
          <div className="text-terminal-text-dim text-xs">2Y</div>
          <div className="font-mono text-lg">{curve.curve['2Y']?.toFixed(2) || 'N/A'}%</div>
        </div>
        <div className="text-center">
          <div className="text-terminal-text-dim text-xs">10Y</div>
          <div className="font-mono text-lg">{curve.curve['10Y']?.toFixed(2) || 'N/A'}%</div>
        </div>
        <div className="text-center">
          <div className="text-terminal-text-dim text-xs">30Y</div>
          <div className="font-mono text-lg">{curve.curve['30Y']?.toFixed(2) || 'N/A'}%</div>
        </div>
      </div>
    </div>
  );
};
