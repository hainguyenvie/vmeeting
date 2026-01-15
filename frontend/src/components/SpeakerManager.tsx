"use client";

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Edit2, Trash2, Users, Check, Search, User } from 'lucide-react';

interface Speaker {
    id: string; // e.g., "SPEAKER_00"
    displayName: string; // e.g., "John Doe" or default "Speaker 1"
    transcriptCount: number;
}

interface KnownPerson {
    id: string; // e.g., "hainh67"
    fullName: string; // e.g., "Nguyễn Hồng Hải"
    title: string; // e.g., "Kĩ sư trí tuệ nhân tạo"
}

// 🔥 Mock database of known people (temporary - will be replaced with real DB)
const KNOWN_PEOPLE: KnownPerson[] = [
    { id: 'hainh67', fullName: 'Nguyễn Hồng Hải', title: 'Kĩ sư trí tuệ nhân tạo' },
    { id: 'lamnh23', fullName: 'Nguyễn Hoàng Lâm', title: 'Kĩ sư trí tuệ nhân tạo' },
    { id: 'vietnh41', fullName: 'Nguyễn Hoàng Việt', title: 'Siêu cấp kĩ sư trí tuệ nhân tạo' }
];

interface SpeakerManagerProps {
    transcripts: Array<{
        speaker?: string;
        text: string;
        sequence_id?: number;
    }>;
    onSpeakerUpdate: (oldSpeaker: string, newName: string) => void;
    onSpeakerMerge: (fromSpeaker: string, toSpeaker: string) => void;
    onClose: () => void;
}

export default function SpeakerManager({
    transcripts,
    onSpeakerUpdate,
    onSpeakerMerge,
    onClose,
}: SpeakerManagerProps) {
    const [speakers, setSpeakers] = useState<Speaker[]>([]);
    const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
    const [editName, setEditName] = useState('');
    const [mergingFrom, setMergingFrom] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [dropdownPosition, setDropdownPosition] = useState<{ top: number; left: number; width: number } | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Update dropdown position when showing
    useEffect(() => {
        if (showSuggestions && inputRef.current) {
            const rect = inputRef.current.getBoundingClientRect();
            setDropdownPosition({
                top: rect.top,
                left: rect.left,
                width: rect.width
            });
        }
    }, [showSuggestions]);

    // Extract unique speakers and count transcripts
    useEffect(() => {
        const speakerMap = new Map<string, number>();

        transcripts.forEach(t => {
            if (t.speaker) {
                speakerMap.set(t.speaker, (speakerMap.get(t.speaker) || 0) + 1);
            }
        });

        const speakerList: Speaker[] = Array.from(speakerMap.entries()).map(([id, count], index) => ({
            id,
            displayName: id.startsWith('SPEAKER_') ? `Speaker ${index + 1}` : id,
            transcriptCount: count,
        }));

        setSpeakers(speakerList.sort((a, b) => b.transcriptCount - a.transcriptCount));
    }, [transcripts]);

    const handleRename = (speakerId: string) => {
        if (editName.trim()) {
            onSpeakerUpdate(speakerId, editName.trim());
            setEditingSpeaker(null);
            setEditName('');
            setSearchQuery('');
            setShowSuggestions(false);
        }
    };

    // Handle selecting from known people
    const handleSelectPerson = (speakerId: string, person: KnownPerson) => {
        const fullNameWithTitle = `${person.fullName} - ${person.title}`;
        setEditName(fullNameWithTitle);
        setSearchQuery('');
        setShowSuggestions(false);
        // Auto-save after selection
        onSpeakerUpdate(speakerId, fullNameWithTitle);
        setEditingSpeaker(null);
    };

    // Filter known people based on search
    const filteredPeople = KNOWN_PEOPLE.filter(person => {
        const query = searchQuery.toLowerCase();
        return person.id.toLowerCase().includes(query) ||
               person.fullName.toLowerCase().includes(query) ||
               person.title.toLowerCase().includes(query);
    });

    const handleMerge = (toSpeaker: string) => {
        if (mergingFrom && mergingFrom !== toSpeaker) {
            onSpeakerMerge(mergingFrom, toSpeaker);
            setMergingFrom(null);
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Users className="w-6 h-6" />
                        <h2 className="text-xl font-bold">Speaker Management</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-white hover:bg-white/20 rounded-full p-2 transition"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content - Allow overflow for dropdown */}
                <div className="p-6 overflow-y-visible max-h-[calc(80vh-8rem)]">
                    {speakers.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                            <Users className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <p className="text-lg">No speakers detected yet</p>
                            <p className="text-sm mt-2">Speakers will appear here after diarization</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {mergingFrom && (
                                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                                    <p className="text-sm font-semibold text-yellow-800 mb-2">
                                        🔀 Merge Mode: Select target speaker
                                    </p>
                                    <p className="text-xs text-yellow-700">
                                        Transcripts from "{speakers.find(s => s.id === mergingFrom)?.displayName}" will be reassigned to the selected speaker
                                    </p>
                                    <button
                                        onClick={() => setMergingFrom(null)}
                                        className="mt-2 text-xs text-yellow-600 hover:text-yellow-800 underline"
                                    >
                                        Cancel merge
                                    </button>
                                </div>
                            )}

                            {speakers.map((speaker, speakerIndex) => (
                                <div
                                    key={speaker.id}
                                    className={`border rounded-lg p-4 transition ${
                                        editingSpeaker === speaker.id ? 'relative z-50' : ''
                                    } ${mergingFrom === speaker.id
                                        ? 'bg-yellow-50 border-yellow-300'
                                        : mergingFrom
                                            ? 'hover:bg-green-50 hover:border-green-300 cursor-pointer'
                                            : 'bg-white border-gray-200 hover:border-indigo-300'
                                        }`}
                                    onClick={() => {
                                        if (mergingFrom && mergingFrom !== speaker.id) {
                                            handleMerge(speaker.id);
                                        }
                                    }}
                                    style={editingSpeaker === speaker.id ? { position: 'relative', zIndex: 9999 } : {}}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex-1">
                                            {editingSpeaker === speaker.id ? (
                                                <div className="flex-1 relative" style={{ zIndex: 9999 }}>
                                                    <div className="flex items-center gap-2 relative z-10">
                                                        <div className="relative flex-1">
                                                            <input
                                                                ref={inputRef}
                                                                type="text"
                                                                value={editName}
                                                                onChange={(e) => {
                                                                    setEditName(e.target.value);
                                                                    setSearchQuery(e.target.value); // 🔥 Auto-search khi gõ
                                                                }}
                                                                onFocus={() => setShowSuggestions(true)} // 🔥 Auto-show khi focus
                                                                onBlur={() => {
                                                                    // Delay to allow click on dropdown items
                                                                    setTimeout(() => setShowSuggestions(false), 200);
                                                                }}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter' && !showSuggestions) handleRename(speaker.id);
                                                                    if (e.key === 'Escape') {
                                                                        setEditingSpeaker(null);
                                                                        setShowSuggestions(false);
                                                                    }
                                                                    if (e.key === 'ArrowDown' && filteredPeople.length > 0) {
                                                                        e.preventDefault();
                                                                        setShowSuggestions(true);
                                                                    }
                                                                }}
                                                                className="border border-indigo-300 rounded px-3 py-2 text-sm font-semibold w-full"
                                                                placeholder="Type to search or enter name..."
                                                                autoFocus
                                                            />
                                                            
                                                            {/* 🔥 Auto-suggest Dropdown - Using Portal to render outside modal */}
                                                            {showSuggestions && filteredPeople.length > 0 && dropdownPosition && createPortal(
                                                                <div 
                                                                    className="fixed bg-white border-2 border-indigo-400 rounded-lg shadow-2xl max-h-80 overflow-y-auto"
                                                                    style={{
                                                                        top: `${dropdownPosition.top - 8}px`,
                                                                        left: `${dropdownPosition.left}px`,
                                                                        width: `${dropdownPosition.width}px`,
                                                                        transform: 'translateY(-100%)',
                                                                        zIndex: 99999
                                                                    }}
                                                                    onMouseDown={(e) => e.preventDefault()} // Prevent input blur
                                                                >
                                                                    {filteredPeople.map(person => (
                                                                        <button
                                                                            key={person.id}
                                                                            onClick={() => handleSelectPerson(speaker.id, person)}
                                                                            className="w-full px-4 py-3 hover:bg-indigo-50 text-left border-b border-gray-100 last:border-0 transition"
                                                                        >
                                                                            <div className="flex items-start gap-2">
                                                                                <User className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
                                                                                <div className="flex-1 min-w-0">
                                                                                    <div className="text-sm font-semibold text-gray-900">
                                                                                        {person.fullName}
                                                                                    </div>
                                                                                    <div className="text-xs text-gray-600">{person.title}</div>
                                                                                    <div className="text-xs text-gray-400 mt-0.5">ID: {person.id}</div>
                                                                                </div>
                                                                            </div>
                                                                        </button>
                                                                    ))}
                                                                </div>,
                                                                document.body
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => handleRename(speaker.id)}
                                                            className="bg-indigo-600 text-white rounded p-2 hover:bg-indigo-700 flex-shrink-0"
                                                            title="Save"
                                                        >
                                                            <Check className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                setEditingSpeaker(null);
                                                                setShowSuggestions(false);
                                                                setSearchQuery('');
                                                            }}
                                                            className="bg-gray-300 text-gray-700 rounded p-2 hover:bg-gray-400 flex-shrink-0"
                                                            title="Cancel"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                    
                                                    {/* Hint text */}
                                                    <p className="text-xs text-gray-500 mt-1">
                                                        💡 Gõ để search: "hai", "lam", "viet"...
                                                    </p>
                                                </div>
                                            ) : (
                                                <div>
                                                    <h3 className="font-bold text-lg text-gray-800">{speaker.displayName}</h3>
                                                    <p className="text-sm text-gray-500">
                                                        {speaker.transcriptCount} transcript{speaker.transcriptCount !== 1 ? 's' : ''}
                                                    </p>
                                                </div>
                                            )}
                                        </div>

                                        {!mergingFrom && editingSpeaker !== speaker.id && (
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => {
                                                        setEditingSpeaker(speaker.id);
                                                        setEditName(speaker.displayName);
                                                    }}
                                                    className="text-indigo-600 hover:bg-indigo-50 rounded p-2 transition"
                                                    title="Rename speaker"
                                                >
                                                    <Edit2 className="w-4 h-4" />
                                                </button>
                                                {speakers.length > 1 && (
                                                    <button
                                                        onClick={() => setMergingFrom(speaker.id)}
                                                        className="text-amber-600 hover:bg-amber-50 rounded p-2 transition"
                                                        title="Merge with another speaker"
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </button>
                                                )}
                                            </div>
                                        )}

                                        {mergingFrom && mergingFrom !== speaker.id && (
                                            <div className="text-green-600 font-semibold text-sm">
                                                Click to merge →
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="bg-gray-50 px-6 py-4 border-t flex justify-between items-center">
                    <p className="text-sm text-gray-600">
                        {speakers.length} speaker{speakers.length !== 1 ? 's' : ''} detected
                    </p>
                    <button
                        onClick={onClose}
                        className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition font-semibold"
                    >
                        Done
                    </button>
                </div>
            </div>
        </div>
    );
}
