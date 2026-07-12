Since the python libraries are installed, make sure to maintain a virtual environment to avoid version conflicts. 

Before start developing for the first time:
(git bash shell - All commands are for git bash shell. May slightly differ depending on your shell type CMD, etc...)

```
cd <your-path-to-project-root-pls REPLACE>/backend
```
```
python -m venv venv
source venv/Scripts/activate
```

Prior to developments in backend(after 1st time):
```
cd backend
source venv/Scripts/activate
```
Once the virtual environment is working, you can see (venv) in the shell after executing any command.

To install/update python libraries:

```
pip install -r requirements.txt
```



To deactivate virtual environment:
```
cd <your-path>/backend
deactivate
```





To stop running server/any code:
```
ctrl + C  (windows)
```
