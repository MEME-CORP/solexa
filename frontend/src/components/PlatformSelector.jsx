import React from 'react';

const PlatformSelector = ({ platform, setPlatform }) => {
  return (
    <div className="mb-6">
      <label className="form-label">Select Platform</label>
      <div className="flex bg-gray-900 p-1 rounded-full">
        <button
          type="button"
          className={`flex-1 py-2 rounded-full ${platform === 'twitter' ? 'bg-purple-600 text-white' : 'text-gray-400'}`}
          onClick={() => setPlatform('twitter')}
        >
          Twitter
        </button>
        <button
          type="button"
          className={`flex-1 py-2 rounded-full ${platform === 'telegram' ? 'bg-purple-600 text-white' : 'text-gray-400'}`}
          onClick={() => setPlatform('telegram')}
        >
          Telegram
        </button>
      </div>
    </div>
  );
};

export default PlatformSelector;