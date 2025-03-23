import React from 'react';

const Header = () => {
  return (
    <header className="mb-12 text-center p-8">
      <h1 className="text-4xl mb-4 font-bold text-white relative">
        <span className="bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-500">
          Social Media Post Writer
        </span>
      </h1>
      <p className="text-lg text-gray-400 max-w-2xl mx-auto">
        Write your post once, let AI style it for different platforms
      </p>
    </header>
  );
};

export default Header;