// api.js - API service for making calls to the Flask backend

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

/**
 * Generate styled content for the specified platform
 * @param {string} message - The user's message to style
 * @param {string} platform - The platform (twitter or telegram)
 * @returns {Promise<Object>} - The styled content response
 */
export const generateStyledContent = async (message, platform) => {
  try {
    const response = await fetch(`${API_URL}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        platform,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to generate content');
    }

    return await response.json();
  } catch (error) {
    console.error('API error:', error);
    throw error;
  }
};