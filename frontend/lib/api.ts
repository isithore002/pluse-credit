// lib/api.ts - Axios client for FastAPI backend

import axios from 'axios';
import { DimensionScores, ScoreResult, Transaction } from './store';

const rawApiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Accept both forms for NEXT_PUBLIC_API_URL:
// - http://localhost:8000
// - http://localhost:8000/api
const normalizedApiBase = rawApiBase.replace(/\/+$/, '').replace(/\/api$/, '');
const API_BASE_URL = normalizedApiBase;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ParseResponse {
  profile_id: string;
  transaction_count: number;
  date_range: {
    start: string;
    end: string;
  };
  transactions: Transaction[];
}

export interface PersonaData {
  id: string;
  name: string;
  archetype: string;
  age: number;
  occupation: string;
  city: string;
  pulse_score: number;
  band: string;
  confidence?: [number, number] | number[];
  dimensions: DimensionScores;
  shap_top3?: Array<{
    feature: string;
    value: number;
    impact: number;
  }>;
}

export const apiService = {
  // Parse statement (PDF/CSV upload)
  async parseStatement(
    file: File,
    bankFormat: string = 'HDFC',
    pdfPassword: string = ''
  ): Promise<ParseResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<ParseResponse>(
      '/api/parse',
      formData,
      {
        params: {
          bank_format: bankFormat,
          ...(pdfPassword ? { pdf_password: pdfPassword } : {}),
        },
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data;
  },

  // Compute score with ML ensemble
  async computeScore(
    profileId: string,
    transactions: Transaction[]
  ): Promise<ScoreResult> {
    const response = await apiClient.post<ScoreResult>('/api/score', {
      profile_id: profileId,
      transactions,
    });

    return response.data;
  },

  // What-if simulation
  async simulateScore(
    profileId: string,
    overrides: Record<string, number>
  ): Promise<ScoreResult> {
    const response = await apiClient.post<ScoreResult>('/api/simulate', {
      profile_id: profileId,
      overrides,
    });

    return response.data;
  },

  // Get demo personas
  async getDemoPersonas(): Promise<PersonaData[]> {
    const response = await apiClient.get<PersonaData[]>('/api/personas');
    return response.data;
  },

  // Get lender PDF report
  async getReport(profileId: string): Promise<Blob> {
    const response = await apiClient.get(`/api/report/${profileId}`, {
      responseType: 'blob',
    });

    return response.data;
  },

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/health');
      return response.status === 200;
    } catch {
      return false;
    }
  },
};

// Handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
    } else if (error.response?.status === 500) {
      console.error('Server error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
