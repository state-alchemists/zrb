package main

import (
	"fmt"
	"os"
)

func main() {
	name := os.Getenv("NAME")
	if name == "" {
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
<<<<<<< HEAD
		// from repo
=======
		// from subrepo
>>>>>>> f0bc2ef0aaef22f25426a88d99447942fcd6755f
>>>>>>> 4412d85d97ab55f906cfca070f93bbe17abe5f27
>>>>>>> 4812fea41c6fc1ae45fb68b9c28459c94728014e
		name = "World"
	}
	fmt.Printf("Hello %s\n", name)
}
