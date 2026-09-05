import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const fetchHealth = async () => {
  const res = await api.get('/health');
  return res.data;
};

export const fetchRecoveries = async () => {
  const res = await api.get('/api/v1/recoveries');
  return res.data;
};

export const fetchRecoveryDetail = async (paymentId: string) => {
  const res = await api.get(`/api/v1/recoveries/${paymentId}`);
  return res.data;
};

export const fetchDemos = async () => {
  const res = await api.get('/api/v1/demos');
  return res.data;
};

export const runDemoScenario = async (scenario: string) => {
  const res = await api.post(`/api/v1/demos/${scenario}/execute`);
  return res.data;
};
