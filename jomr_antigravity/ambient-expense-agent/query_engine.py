import vertexai
from vertexai.preview import reasoning_engines

def main():
    vertexai.init(project='project-a3eb1889-fbc0-4f8e-a9a', location='us-east1')
    try:
        print("Loading engine...")
        engine = reasoning_engines.ReasoningEngine('projects/project-a3eb1889-fbc0-4f8e-a9a/locations/us-east1/reasoningEngines/7474814297156091904')
        print("Engine loaded.")
        print("GCA Resource:", engine.gca_resource)
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
