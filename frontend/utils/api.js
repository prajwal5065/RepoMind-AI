import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api',
  timeout: 120000,
});

export const uploadRepo = async (file, sessionId) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);

  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const parseRepo = async (sessionId) => {
  const response = await api.post(`/parse/${sessionId}`);
  return response.data;
};

export const indexRepo = async (sessionId) => {
  const response = await api.post(`/index/${sessionId}`);
  return response.data;
};

export const getAnalysis = async (sessionId, provider = '') => {
  const response = await api.get(`/analyze/${sessionId}`, {
    headers: provider ? { 'X-LLM-Provider': provider } : {},
  });
  return response.data;
};

export const getDocs = async (sessionId, provider = '') => {
  const response = await api.post(`/docs/${sessionId}`, {}, {
    headers: provider ? { 'X-LLM-Provider': provider } : {},
  });
  return response.data;
};

export const cloneRepo = async (repoUrl) => {
  const response = await api.post('/clone-repo', { repo_url: repoUrl });
  return response.data;
};

export const chatStreamUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/chat`;
