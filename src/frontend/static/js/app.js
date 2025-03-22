// Main application component
function App() {
    return (
      <div className="container">
        <h1>Playful Gamification Mobile Interface</h1>
        <p>A modern, vibrant, and friendly mobile interface design system that employs gamification elements to engage users.</p>
        
        <section id="dashboard">
          <h2>Dashboard</h2>
          <div className="row">
            <div className="col-4">
              <Card variant="primary">
                <CardHeader>Daily Tasks</CardHeader>
                <CardBody>
                  <h4>3 tasks remaining</h4>
                  <p>Complete your daily tasks to earn rewards!</p>
                  <Button>View Tasks</Button>
                </CardBody>
              </Card>
            </div>
            
            <div className="col-4">
              <Card variant="secondary-1">
                <CardBody>
                  <h4>Weekly Challenge</h4>
                  <p>You're 60% through this week's challenge</p>
                  <div className="progress mb-2">
                    <div className="progress-bar" style={{ width: '60%', backgroundColor: 'var(--color-secondary-1)' }}></div>
                  </div>
                  <Button variant="secondary-1">Continue</Button>
                </CardBody>
              </Card>
            </div>
            
            <div className="col-4">
              <Card variant="accent">
                <CardHeader>Rewards</CardHeader>
                <CardBody>
                  <h4>250 Points</h4>
                  <p>You've earned enough for a reward!</p>
                  <Button variant="accent">Claim Reward</Button>
                </CardBody>
                <CardFooter>
                  <small className="text-light">Last updated 3 mins ago</small>
                </CardFooter>
              </Card>
            </div>
          </div>
        </section>
        
        {/* Add more sections as needed */}
      </div>
    );
  }
  
  // Render the main app component
  ReactDOM.render(<App />, document.getElementById('root'));