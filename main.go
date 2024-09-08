package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
<<<<<<< HEAD
		// from repo
=======
		// from subrepo
>>>>>>> f0bc2ef0aaef22f25426a88d99447942fcd6755f
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
