import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TripList from './components/TripList';
import TripDetail from './components/TripDetail';
import TripForm from './components/TripForm';
import TripAnalysis from './components/TripAnalysis';
import TripTimeline from './components/TripTimeline';
import TripImport from './components/TripImport';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-100">
          <nav className="bg-blue-600 text-white p-4 shadow">
            <div className="container mx-auto flex justify-between items-center">
              <Link to="/trips" className="text-2xl font-bold">✈️ travelops</Link>
              <div className="flex items-center gap-2">
                <Link to="/trips/import" className="bg-blue-700 px-4 py-1 rounded text-sm hover:bg-blue-800">
                  Import
                </Link>
                <Link to="/trips" className="bg-blue-700 px-4 py-1 rounded text-sm hover:bg-blue-800">
                  Dashboard
                </Link>
              </div>
            </div>
          </nav>
          <div className="container mx-auto">
            <Routes>
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<TripForm />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/analysis" element={<TripAnalysis />} />
              <Route path="/trips/:id/timeline" element={<TripTimeline />} />
              <Route path="/trips/:id/edit" element={<TripForm />} />
              <Route path="/trips/import" element={<TripImport />} />
              <Route path="/" element={<TripList />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;