package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	// Get configurations
	appPort := os.Getenv("APP_PORT")
	if appPort == "" {
		appPort = "8080"
	}
	appMessage := os.Getenv("APP_MESSAGE")
	if appMessage == "" {
		appMessage = "Hello world"
	}

	// Define handler
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, appMessage)
	})
	// Listen and serve
	fmt.Printf("Listening on port %s\n", appPort)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", appPort), nil))
}
