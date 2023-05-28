<script lang="ts">
    export let data: any[] = [];
    export let captionKey: string = '';
    export let separator: string = ', '

    function rowToStr(row: any): string {
        if (captionKey == '') {
            return JSON.stringify(row)
        }
        return row[captionKey];
    }

    function dataToStr(data: any[]) {
        data.map((row) => rowToStr(row)).join(separator)
    }
</script>
{#each data as row}
    <div class="badge" {...$$restProps}>{rowToStr(row)}</div>
{/each}
