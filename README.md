# Underground & HireMe Chatbots with IBM Watson 

This is our presentation for the demo day of the Cognitive Builder Faire.

**********
NOTICE: This app was build using a trial version of IBM Watson's Chat capabilities, it may no longer function properly by the time you use it
**********

To run:

1. Import the Watson Conversation workspace from conversation/workspace.json into your Watson Conversation service.

Python:

1. cd into the python directory
2. Rename .env.template to .env
3. Add your Watson Conversation credentials to .env
4. Create a virtual environment by running `virtualenv venv`
5. Activate the virtual environment by running `source ./venv/bin/activate`
6. Install dependencies by running `pip install -r requirements.txt`
7. Run `python app.py` 

To run simply clone this repo, cd into the presentation directory, install npm dependencies ([reveal.js](http://lab.hakim.se/reveal-js/)), and type `npm start`:

```
git clone https://github.com/matthew-mcateer/CBF-MassChallenge-Hackathon-2017/chatbot-presentation
cd cbf-chatbot-presentation
npm install
npm start
```

Open the browser and go to http://localhost:8000.
