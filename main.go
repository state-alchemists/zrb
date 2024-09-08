package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
		// from repo
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
