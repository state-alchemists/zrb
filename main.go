package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
<<<<<<< HEAD
		// change by repo
=======
		// Change by subrepo
>>>>>>> d75eb33cf7e6974515c56bd47e3feb475fb38e78
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
