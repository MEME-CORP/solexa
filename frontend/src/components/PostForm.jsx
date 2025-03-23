import React, { useState } from 'react';
import PlatformSelector from './PlatformSelector';
import MessageInput from './MessageInput';
import SubmitButton from './SubmitButton';

const PostForm = ({ onSubmit, isLoading }) => {
  const [message, setMessage] = useState('');
  const [platform, setPlatform] = useState('twitter');
  const maxLength = platform === 'twitter' ? 280 : 4000;
  
  const isFormValid = message.trim() !== '' && message.length <= maxLength;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isFormValid) {
      onSubmit({ message, platform });
    }
  };

  return (
    <div className="card">
      <form onSubmit={handleSubmit}>
        <PlatformSelector platform={platform} setPlatform={setPlatform} />
        <MessageInput message={message} setMessage={setMessage} maxLength={maxLength} />
        <SubmitButton 
          isDisabled={!isFormValid}
          isLoading={isLoading}
          onClick={handleSubmit}
        />
      </form>
    </div>
  );
};

export default PostForm;