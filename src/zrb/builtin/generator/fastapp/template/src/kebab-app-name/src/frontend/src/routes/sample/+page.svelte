<script lang="ts">
    let data = [
        {"id": "abc", "name": "Cy Ganderton", "job": "Quality Control Specialist", "favorite_color": "Blue"},
        {"id": "def", "name": "Hart Hagerty", "job": "Desktop Support Tehcnician", "favorite_color": "Purple"},
        {"id": "ghi", "name": "Brice Syre", "job": "Tax Accountant", "favorite_color": "Red"},
    ]
</script>
<div class="overflow-x-auto">
    <table class="table w-full">
        <!-- head -->
        <thead>
            <tr>
                <th></th>
                <th>Name</th>
                <th>Job</th>
                <th>Favorite Color</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {#each data as row}
                <tr>
                    <th>{row.id}</th>
                    <td>{row.name}</td>
                    <td>{row.job}</td>
                    <td>{row.favorite_color}</td>
                    <td>
                        <a class="btn" href="insert/{row.id}">Insert</a>
                        <a class="btn" href="update/{row.id}">Update</a>
                        <a class="btn btn-accent" href="delete/{row.id}">Delete</a>
                    </td>
                </tr>
            {/each}
        
        </tbody>
    </table>
</div>