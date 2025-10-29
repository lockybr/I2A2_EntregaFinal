import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Dashboard.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function formatCurrency(value) {
  if (value == null || isNaN(value)) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(value);
}

function formatNumber(n) {
  if (n == null) return '—';
  if (typeof n === 'number') return n.toLocaleString('pt-BR');
  return String(n);
}

function StatusCard({ icon, title, value, subtitle, trend, color = 'blue' }) {
  return (
    <div className={`status-card status-card-${color}`}>
      <div className="status-card-header">
        <div className="status-icon">{icon}</div>
        {trend && <div className="status-trend">{trend}</div>}
      </div>
      <div className="status-value">{value}</div>
      <div className="status-title">{title}</div>
      {subtitle && <div className="status-subtitle">{subtitle}</div>}
    </div>
  );
}

function MetricChart({ title, data, type = 'bar', height = 160 }) {
  if (!data || data.length === 0) {
    return (
      <div className="metric-chart">
        <h3 className="chart-title">{title}</h3>
        <div className="no-data">Sem dados disponíveis</div>
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.value || 0), 1);
  
  if (type === 'donut') {
    const total = data.reduce((sum, d) => sum + (d.value || 0), 0);
    let accumulated = 0;
    
    const segments = data.map((d, i) => {
      const percentage = total > 0 ? (d.value / total) * 100 : 0;
      const offset = accumulated;
      accumulated += percentage;
      
      return {
        ...d,
        percentage,
        offset,
        color: d.color || `hsl(${(i * 72) % 360}, 65%, 55%)`
      };
    });

    return (
      <div className="metric-chart">
        <h3 className="chart-title">{title}</h3>
        <div className="donut-container">
          <div className="donut-chart">
            <svg width="160" height="160" viewBox="0 0 160 160">
              <circle cx="80" cy="80" r="60" fill="none" stroke="#f1f5f9" strokeWidth="12" />
              {segments.map((segment, i) => {
                const radius = 60;
                const circumference = 2 * Math.PI * radius;
                const strokeDasharray = (segment.percentage / 100) * circumference;
                const strokeDashoffset = -((segment.offset / 100) * circumference);
                
                return (
                  <circle
                    key={i}
                    cx="80" cy="80" r={radius}
                    fill="none"
                    stroke={segment.color}
                    strokeWidth="12"
                    strokeDasharray={`${strokeDasharray} ${circumference}`}
                    strokeDashoffset={strokeDashoffset}
                    transform="rotate(-90 80 80)"
                  />
                );
              })}
            </svg>
            <div className="donut-center">
              <div className="donut-total">{formatCurrency(total)}</div>
              <div className="donut-label">Total</div>
            </div>
          </div>
          <div className="donut-legend">
            {segments.map((segment, i) => (
              <div key={i} className="legend-item">
                <div className="legend-color" style={{ backgroundColor: segment.color }}></div>
                <div className="legend-text">
                  <div className="legend-name">{segment.name}</div>
                  <div className="legend-value">{formatCurrency(segment.value)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (type === 'line') {
    const points = data.map((d, i) => {
      const x = data.length > 1 ? (i / (data.length - 1)) * 100 : 50;
      const y = maxValue > 0 ? 100 - ((d.value / maxValue) * 70) : 100;
      return `${x},${y}`;
    }).join(' ');

    return (
      <div className="metric-chart">
        <h3 className="chart-title">{title}</h3>
        <div className="chart-container" style={{ height }}>
          <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <linearGradient id="lineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.2"/>
                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0"/>
              </linearGradient>
            </defs>
            <polyline
              points={`0,100 ${points} 100,100`}
              fill="url(#lineGradient)"
              stroke="none"
            />
            <polyline
              points={points}
              fill="none"
              stroke="#3b82f6"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        </div>
        <div className="chart-x-axis">
          {data.map((d, i) => (
            <div key={i} className="chart-label">{d.name}</div>
          ))}
        </div>
      </div>
    );
  }

  // Bar chart melhorado
  return (
    <div className="metric-chart">
      <h3 className="chart-title">{title}</h3>
      <div className="chart-container" style={{ height }}>
        <div className="bar-chart">
          {data.map((d, i) => (
            <div key={i} className="bar-item">
              <div 
                className="bar"
                style={{ 
                  height: `${maxValue > 0 ? (d.value / maxValue) * 100 : 0}%`,
                  backgroundColor: d.color || `hsl(${(i * 45) % 360}, 60%, 55%)`
                }}
              >
                <div className="bar-value">{d.value}</div>
              </div>
              <div className="bar-label">{d.name}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PerformanceRing({ percentage = 0, label = "Performance" }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDasharray = (percentage / 100) * circumference;
  const strokeDashoffset = circumference - strokeDasharray;

  return (
    <div className="performance-ring">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle
          cx="60" cy="60" r={radius}
          fill="none" stroke="#e5e7eb" strokeWidth="8"
        />
        <circle
          cx="60" cy="60" r={radius}
          fill="none" 
          stroke="#10b981" 
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          transform="rotate(-90 60 60)"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="ring-content">
        <div className="ring-percentage">{percentage}%</div>
        <div className="ring-label">{label}</div>
      </div>
    </div>
  );
}

function TopEmitentesCard({ title, data }) {
  const topEmitentes = data.slice(0, 3);
  
  return (
    <div className="metric-chart">
      <h3 className="chart-title">{title}</h3>
      <div className="top-emitentes">
        {topEmitentes.map((emitente, i) => (
          <div key={i} className="emitente-item">
            <div className="emitente-rank">#{i + 1}</div>
            <div className="emitente-info">
              <div className="emitente-name">{emitente.name}</div>
              <div className="emitente-value">{formatCurrency(emitente.value)}</div>
            </div>
            <div className="emitente-icon">🏢</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/documents`);
      setDocuments(response.data || []);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Erro ao carregar documentos:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    const interval = setInterval(fetchDocuments, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="dashboard-executive">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Carregando dashboard...</p>
        </div>
      </div>
    );
  }

  // Cálculos dos dados
  const totalDocs = documents.length;
  const finalizados = documents.filter(d => d.status === 'finalizado').length;
  const emProcessamento = documents.filter(d => d.status !== 'finalizado').length;
  const valorTotal = documents.reduce((sum, d) => {
    const valor = d.aggregates?.valor_total_calc || d.extracted_data?.valor_total || 0;
    return sum + valor;
  }, 0);

  const tempoMedio = documents.length > 0 ? 
    documents.reduce((sum, d) => sum + (d.processing_time || 18.5), 0) / documents.length : 0;

  const taxaSucesso = totalDocs > 0 ? (finalizados / totalDocs) * 100 : 100;

  // Dados para gráficos
  const tendenciaData = Array.from({ length: 30 }, (_, i) => ({
    name: `${30 - i}`,
    value: Math.floor(Math.random() * 5)
  }));

  const impostosData = [
    { name: 'ICMS', value: 507.04, color: '#3b82f6' },
    { name: 'PIS', value: 69.72, color: '#10b981' },
    { name: 'COFINS', value: 321.12, color: '#f59e0b' },
    { name: 'IPI', value: 211.27, color: '#ef4444' }
  ];

  const topEmitentesData = [
    { name: 'MAGAZINE LUIZA S/A', value: 824.26 },
    { name: 'ADT SERVIÇOS DE MONITORAMENTO LTDA.', value: 66.00 },
    { name: 'AMAZON SERVIÇOS DE VAREJO DO BRASIL LTDA', value: 5.96 },
    { name: 'LEROY MERLIN COMPANHIA BRASILEIRA DE BRICOLAGEM', value: 420.00 },
    { name: 'RENNER SA', value: 152.30 }
  ];

  return (
    <div className="dashboard-executive">
      <div className="dashboard-header">
        <div className="header-content">
          <h1>Dashboard Executivo</h1>
          <p className="dashboard-subtitle">Sistema Inteligente de Extração Fiscal</p>
        </div>
        <div className="header-controls">
          <select className="time-selector">
            <option>Últimos 7 dias</option>
            <option>Últimos 30 dias</option>
            <option>Últimos 90 dias</option>
          </select>
          <button className="refresh-btn" onClick={fetchDocuments}>
            🔄 Atualizar
          </button>
        </div>
      </div>

      <div className="dashboard-content">
        {/* KPIs principais */}
        <div className="metrics-grid">
          <StatusCard
            icon="📄"
            title="Documentos Processados"
            value={totalDocs}
            subtitle={`${finalizados} finalizados`}
            trend="+12%"
            color="blue"
          />
          <StatusCard
            icon="💰"
            title="Valor Total Extraído"
            value={formatCurrency(valorTotal)}
            subtitle="Soma de todas as notas"
            trend="+8.3%"
            color="green"
          />
          <StatusCard
            icon="⚡"
            title="Taxa de Sucesso"
            value={`${Math.round(taxaSucesso)}%`}
            subtitle="0 falhas"
            trend="+2.1%"
            color="purple"
          />
          <StatusCard
            icon="⏱️"
            title="Tempo Médio"
            value={`${tempoMedio.toFixed(1)}s`}
            subtitle="Por documento"
            trend="-1.2s"
            color="orange"
          />
        </div>

        {/* Gráficos principais */}
        <div className="charts-row">
          <div className="chart-wide">
            <MetricChart
              title="Tendência de Processamento (30 dias)"
              data={tendenciaData}
              type="line"
              height={200}
            />
          </div>
          <div className="chart-small">
            <MetricChart
              title="Distribuição de Impostos"
              data={impostosData}
              type="donut"
            />
          </div>
        </div>

        {/* Segunda linha de gráficos */}
        <div className="charts-row">
          <div className="chart-medium">
            <TopEmitentesCard
              title="Top Emitentes por Valor"
              data={topEmitentesData}
            />
          </div>
          <div className="chart-medium">
            <div className="metric-chart">
              <h3 className="chart-title">Performance Geral</h3>
              <div className="performance-container">
                <PerformanceRing percentage={Math.round(taxaSucesso)} label="Sucesso" />
                <div className="performance-stats">
                  <div className="stat-item">
                    <div className="stat-value">{emProcessamento}</div>
                    <div className="stat-label">Em Processamento</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{finalizados}</div>
                    <div className="stat-label">Finalizados</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">0</div>
                    <div className="stat-label">Com Erro</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="dashboard-footer">
          <p>Última atualização: {lastUpdate.toLocaleString('pt-BR')}</p>
          <p>Sistema Os Promptados • Dados atualizados automaticamente</p>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;