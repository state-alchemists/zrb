package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
		// Add default value (subrepo)
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
