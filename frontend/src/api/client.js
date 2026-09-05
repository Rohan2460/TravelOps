import axios from 'axios';

const apiClient = axios.create({
    baseURL: '/api', // proxied to Django (see vite.config.js -> server.proxy)
    headers: {
        'Content-Type': 'application/json',
    },
});

export default apiClient;