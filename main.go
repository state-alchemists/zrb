package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
		// Change by subrepo
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
