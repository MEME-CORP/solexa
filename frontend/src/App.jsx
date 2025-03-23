import React from 'react';
import Header from './components/Header';
import PostForm from './components/PostForm';
import Preview from './components/Preview';
import HowItWorks from './components/HowItWorks';
import { generateStyledContent } from './services/api';

const App = () => {
  const [message, setMessage] = React.useState('');
  const [platform, setPlatform] = React.useState('twitter');
  const [isLoading, setIsLoading] = React.useState(false);
  const [styledContent, setStyledContent] = React.useState('');
  const [error, setError] = React.useState(null);

  const handleGenerateContent = async (formData) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Call the API to generate styled content
      const result = await generateStyledContent(formData.message, formData.platform);
      
      setStyledContent(result.styled_content);
      
    } catch (err) {
      console.error('Error generating styled content:', err);
      setError('Failed to generate styled content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Header />
        
        <main>
          <PostForm onSubmit={handleGenerateContent} isLoading={isLoading} />
          
          {error && (
            <div className="bg-red-900/30 border border-red-800 text-red-200 p-4 rounded-md mb-6">
              {error}
            </div>
          )}
          
          {styledContent && (
            <Preview styledContent={styledContent} platform={platform} />
          )}
          
          <HowItWorks />
        </main>
        
        <footer className="mt-12 text-center text-gray-500 text-sm">
          <p>Integrated with your existing AI codebase &copy; {new Date().getFullYear()}</p>
        </footer>
      </div>
    </div>
  );
};

export default App;