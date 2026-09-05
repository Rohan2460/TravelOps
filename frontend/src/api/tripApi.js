import apiClient from './client';

export const getTrips = async () => {
  const response = await apiClient.get('/trips/');
  return response.data;
};

export const getTrip = async (id) => {
  const response = await apiClient.get(`/trips/${id}/`);
  return response.data;
};

export const createTrip = async (tripData) => {
  const response = await apiClient.post('/trips/', tripData);
  return response.data;
};

export const updateTrip = async ({ id, data }) => {
  const response = await apiClient.put(`/trips/${id}/`, data);
  return response.data;
};

export const deleteTrip = async (id) => {
  await apiClient.delete(`/trips/${id}/`);
};

export const getTripAnalysis = async (id) => {
  const response = await apiClient.get(`/trips/${id}/analysis/`);
  return response.data;
};

export const extractTrip = async ({ file, model }) => {
  const formData = new FormData();
  formData.append('file', file);
  if (model) formData.append('model', model);
  const response = await apiClient.post('/trips/import/extract/', formData);
  return response.data;
};

export const confirmTrip = async (payload) => {
  const response = await apiClient.post('/trips/import/confirm/', payload);
  return response.data;
};