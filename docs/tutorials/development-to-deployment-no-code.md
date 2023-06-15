🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Development to deployment: No code

```bash
# Create a project
zrb project create --project-dir my-project --project-name "My Project"
cd my-project

# Create a Fastapp
zrb project add fastapp --project-dir . --app-name "fastapp" --http-port 3000

# Add library module to fastapp
zrb project add fastapp-module --project-dir . --app-name "fastapp" --module-name "library"

# Add entity named "books"
zrb project add fastapp-crud --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --plural-entity-name "books" --column-name "code"

# Add column to the entity
zrb project add fastapp-field --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --column-name "title" --column-type "str"

# Run Fastapp as monolith
zrb project start-fastapp --fastapp-run-mode "monolith"

# Run Fastapp as microservices
zrb project start-fastapp --fastapp-run-mode "microservices"

# Run Fastapp as container
zrb project start-fastapp-container --fastapp-run-mode "microservices"
zrb project stop-fastapp-container

# Deploy fastapp
docker login
zrb project deploy-fastapp --fastapp-deploy-mode "microservices"
```


🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
