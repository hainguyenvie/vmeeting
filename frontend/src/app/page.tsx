'use client'

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';

interface Meeting {
  id: string;
  title: string;
  created_at: number;
  duration?: number;
  summary?: string;
}

export default function HomePage() {
  const router = useRouter();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await meetingsAPI.getAll();
      setMeetings(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load meetings');
      console.error('Error loading meetings:', err);
    } finally {
      setLoading(false);
    }
  };

  const createMeeting = async () => {
    try {
      const newMeeting = await meetingsAPI.create({
        title: `Meeting ${new Date().toLocaleString()}`
      });
      setMeetings([newMeeting, ...meetings]);
      // Navigate to new meeting detail
      router.push(`/meeting/${newMeeting.id}`);
    } catch (err: any) {
      alert('Failed to create meeting: ' + err.message);
    }
  };

  const handleMeetingClick = (meetingId: string) => {
    router.push(`/meeting/${meetingId}`);
  };

  const handleDeleteMeeting = async (meetingId: string, meetingTitle: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click

    if (!confirm(`Are you sure you want to delete "${meetingTitle}"?\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      await meetingsAPI.delete(meetingId);
      // Remove from local state
      setMeetings(meetings.filter(m => m.id !== meetingId));
      alert('Meeting deleted successfully');
    } catch (err: any) {
      alert('Failed to delete meeting: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Meeting Minutes</h1>
            <p className="text-gray-600 mt-1">Web Version - Beta</p>
          </div>
          <button
            onClick={createMeeting}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium shadow-sm"
          >
            + New Meeting
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
            <p className="mt-4 text-gray-600">Loading meetings...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg mb-4">
            <p className="font-semibold">Error loading meetings</p>
            <p className="text-sm mt-1">{error}</p>
            <button
              onClick={loadMeetings}
              className="text-sm underline mt-2"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && meetings.length === 0 && (
          <div className="text-center py-16 bg-white rounded-lg border-2 border-dashed border-gray-300">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">No meetings yet</h3>
            <p className="mt-2 text-gray-600">Click "New Meeting" to get started</p>
          </div>
        )}

        {/* Meetings Grid */}
        {!loading && meetings.length > 0 && (
          <div className="grid gap-4">
            {meetings.map((meeting) => (
              <div
                key={meeting.id}
                onClick={() => handleMeetingClick(meeting.id)}
                className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg hover:border-blue-300 transition cursor-pointer group"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg text-gray-900 group-hover:text-blue-600">
                      {meeting.title}
                    </h3>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        {new Date(meeting.created_at * 1000).toLocaleString('vi-VN', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                      {meeting.duration && (
                        <span className="flex items-center gap-1">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {Math.round(meeting.duration)} min
                        </span>
                      )}
                    </div>
                    {meeting.summary && (
                      <p className="mt-3 text-gray-700 line-clamp-2">
                        {meeting.summary}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Delete Button */}
                    <button
                      onClick={(e) => handleDeleteMeeting(meeting.id, meeting.title, e)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                      aria-label="Delete meeting"
                      title="Delete meeting"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                    {/* Chevron Arrow */}
                    <svg className="w-5 h-5 text-gray-400 group-hover:text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Banner */}
        <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-blue-900">Web Version (Beta)</h4>
              <p className="text-sm text-blue-800 mt-1">
                Click any meeting to view details and transcripts. Recording and real-time transcription features are being added.
              </p>
              <p className="text-xs text-blue-700 mt-2">
                Backend API: <code className="bg-blue-100 px-1 py-0.5 rounded">{process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5167'}</code>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
