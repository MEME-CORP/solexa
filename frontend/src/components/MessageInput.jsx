import React from 'react';

const MessageInput = ({ message, setMessage, maxLength }) => {
  const characterCount = message.length;
  const isOverLimit = characterCount > maxLength;

  return (
    <div className="mb-6">
      <label className="form-label" htmlFor="message">
        Your Message
      </label>
      <textarea
        id="message"
        className="form-input"
        rows="6"
        placeholder="Write your post here..."
        value={message}
        onChange={(e) => setMessage(e.target.value)}
      />
      <div className={`mt-2 text-sm flex justify-between ${isOverLimit ? 'text-red-400' : 'text-gray-500'}`}>
        <span>Characters: {characterCount}/{maxLength}</span>
        {isOverLimit && <span>Character limit exceeded</span>}
      </div>
    </div>
  );
};

export default MessageInput;