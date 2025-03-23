import React from 'react';

const SubmitButton = ({ isDisabled, isLoading, onClick }) => {
  return (
    <button
      type="button"
      className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-500 text-white font-semibold rounded-full hover:opacity-90 transition shadow-md disabled:opacity-50"
      disabled={isDisabled || isLoading}
      onClick={onClick}
    >
      {isLoading ? 'Generating...' : 'Generate Styled Post'}
    </button>
  );
};

export default SubmitButton;