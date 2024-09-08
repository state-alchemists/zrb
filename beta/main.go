package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
		// Comment from main repo
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
